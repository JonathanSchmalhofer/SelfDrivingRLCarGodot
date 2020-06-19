extends KinematicBody2D

################################################################################
### Constants

# Other
const game_factor : float = 4.2 # increase real dynamics to be more game like, manually tuned

# Input
const throttle_rise_factor : float = 0.2
const throttle_fall_factor : float = -0.3
const brake_rise_factor : float = 0.3
const brake_fall_factor : float = -0.4
const steering_rise_factor : float = 0.08
const steering_fall_factor : float = 0.2
const max_steering : float = 0.8

# Vehicle and World Parameters
const torque_engine_max : float = 180.0 * game_factor # make acceleration more arcade like
const i_differential : float = 4.1
const i_gear : float = 1.5 # no gear shifting implemented
const r_wheel : float = 0.31
const mass_vehicle : float = 750.0
const c_w : float = 0.91
const rho : float = 1.205
const area : float = 1.72
const rolling_resistance : float = 1.5
const gravity : float = 9.81
const friction_coefficient : float = 1.2 * game_factor # make braking more arcade like
const l_r : float = 7.0 # non realistic, adapted to pixel-size of vehicle
const l_f : float = 4.0 # non realistic, adapted to pixel-size of vehicle
const diag_factor : float = 1/sqrt(2)
const sensor_directions : Array = [Vector2(0.0,1.0), Vector2(diag_factor,diag_factor), Vector2(1.0,0.0), Vector2(diag_factor,-diag_factor), Vector2(0.0,-1.0)]
const sensor_range : float = 100.0

################################################################################
### Varibles

# Inputs
var throttle : float = 0.0
var brake : float = 0.0
var steering : float = 0.0

# Inputs from External
var throttle_external : float = 0.001
var brake_external : float = 0.0
var steering_external : float = 0.0


# Intermediate States
var force_drive : float = 0.0

# States of Kinematic Model
var velocity_longitudinal : float = 0.0
var x_dot : float = 0.0
var y_dot : float = 0.0
var psi : float = 0.0

# Sensor
var sensor_readings : Array = [0.0, 0.0, 0.0, 0.0, 0.0]
var sensor_hits : Array = [Vector2(0.0, 0.0), Vector2(0.0, 0.0), Vector2(0.0, 0.0), Vector2(0.0, 0.0), Vector2(0.0, 0.0)]

# Other
var delta_step : float = 0.1 # 100 ms
var id : String
var manual_control : bool = false
var received_step_command : bool = false
var server_node


################################################################################
### Signals

signal sense_response(uuid, sensor_0, sensor_1, sensor_2, sensor_3, sensor_4, velocity, yaw, pos_x, pos_y)

################################################################################
### Functions

func _ready():
	server_node = get_node("/root/Node2D/Server")
	server_node.connect("command_step", self, "_on_command_step")

func _physics_process(delta):
	if manual_control or received_step_command:
		received_step_command = false
		GetAndCalcInput(delta)
		CalcDrivingForces()
		CalcKinematicModel()
		UpdateNodes()
		CalcSensors()
		SendReponse()
		self.update()

func _draw():
	DrawSensors()

func _on_command_step():
	#print("Got Step command")
	received_step_command = true

func GetAndCalcInput(delta):
	if (manual_control):
		delta_step = delta
		GetAndCalcUserInput()
	else:
		GetExternalInput()

func GetAndCalcUserInput():
	# Determine Inputs from User
	var throttle_delta : float = throttle_fall_factor # if nothing is pressed, the throttle will gradually go back to zero
	var brake_delta : float = brake_fall_factor
	var steering_delta : float = -1 * sign(steering) * min(steering_fall_factor, abs(steering))
	if Input.is_action_pressed("ui_up"):
		throttle_delta = throttle_rise_factor
	if Input.is_action_pressed("ui_down"):
		brake_delta = brake_rise_factor
	if Input.is_action_pressed("ui_left"):
		steering_delta = -1 * steering_rise_factor
	if Input.is_action_pressed("ui_right"):
		steering_delta = steering_rise_factor
	# Calculate Inputs to the Dynamic System based on Inputs we got
	throttle += throttle_delta
	throttle = clamp(throttle, 0, 1) # throttle ranges from [0;1]
	brake += brake_delta
	brake = clamp(brake, 0, 1) # brake ranges from [0;1]
	steering += steering_delta
	steering = clamp(steering, -max_steering, max_steering)

func GetExternalInput():
	throttle = clamp(throttle_external, 0, 1) # throttle ranges from [0;1]
	brake = clamp(brake_external, 0, 1) # brake ranges from [0;1]
	steering = clamp(steering_external, -max_steering, max_steering)
	

func CalcDrivingForces():
	var force_engine : float = throttle * torque_engine_max * i_differential * i_gear / r_wheel
	var force_brake : float = -1 * brake * mass_vehicle * gravity * friction_coefficient * sign(velocity_longitudinal)
	var force_rolling : float = -1 * rolling_resistance * velocity_longitudinal
	var force_drag : float = -1 * 0.5 * c_w * rho * area * velocity_longitudinal * velocity_longitudinal * sign(velocity_longitudinal)
	force_drive = force_engine + force_brake + force_rolling + force_drag

func CalcKinematicModel():
	var acceleration : float = force_drive / mass_vehicle
	velocity_longitudinal += acceleration * delta_step
	# todo: psi_dot, betao
	var beta : float = atan(l_r/(l_r+l_f) * tan(steering))
	var psi_dot : float = velocity_longitudinal/l_r * sin(beta)
	psi += psi_dot * delta_step * game_factor
	x_dot = velocity_longitudinal * cos(psi+beta)
	y_dot = velocity_longitudinal * sin(psi+beta)

func UpdateNodes():
	var velocity : Vector2 = Vector2.ZERO
	velocity.x = x_dot * game_factor
	velocity.y = y_dot * game_factor
	#velocity = move_and_slide(velocity)
	var collision = move_and_collide(velocity * delta_step)
	if collision:
		velocity = velocity.slide(collision.normal)
	# using move_and_slide
	velocity = move_and_slide(velocity)
	rotation = psi

func CalcSensors():
	var space_state = get_world_2d().direct_space_state
	for idx in sensor_directions.size():
		var direction = sensor_directions[idx]
		var target_position = position + direction.rotated(rotation) * sensor_range
		var result = space_state.intersect_ray(position, target_position, [self], collision_mask) # ray casting happens in world coordinates, thus scale already is taken into account
		if result:
			target_position = result.position
		sensor_readings[idx] = (target_position-position).length()

func DrawSensors():
	for idx in sensor_directions.size():
		var target = sensor_directions[idx] * sensor_readings[idx]
		self.draw_line(Vector2(0.0, 0.0), target/scale, Color(1, 0, 0, 1), 1.0, true) # this scene is scaled, so drawing must be scaled too

func SetId(_id):
	id = _id

func GetId():
	return id

func SetManualControl(val):
	manual_control = val

func GetManualControl():
	return manual_control

func SetExternalInputs(_throttle, _brake, _steering):
	#print("Setting External Inputs")
	throttle_external = _throttle
	brake_external = _brake
	steering_external = _steering

func SendReponse():
	if not manual_control:
		sensor_readings
		emit_signal("sense_response", id, sensor_readings[0], sensor_readings[1], sensor_readings[2], sensor_readings[3], sensor_readings[4], velocity_longitudinal, psi, position.x, position.y)
