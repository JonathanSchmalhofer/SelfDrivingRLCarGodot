extends KinematicBody2D

################################################################################
### Constants

# Other
const game_factor : float = 3.0 # increase real dynamics to be more game like, manually tuned
const grid_size_rows : int = 84
const grid_size_cols : int = 84

# Input
const throttle_rise_factor : float = 0.2
const throttle_fall_factor : float = -0.3
const brake_rise_factor : float = 0.3
const brake_fall_factor : float = -0.4
const steering_rise_factor : float = 0.08
const steering_fall_factor : float = 0.2
const max_steering : float = 1.0

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
const step_size : float = 0.1 # 100 ms

################################################################################
### Varibles

# Inputs
var throttle : float = 0.0
var brake : float = 0.0
var steering : float = 0.0

# Inputs from External
var throttle_external : float = 0.0
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
var sensor_screenshot : Image

# Other
var step_counter : float = 0.0
var distance_counter : float = 0.0
var delta_step : float = step_size
var id : String
var manual_control : bool = false
var received_step_command : bool = false
var game_logic_node
var action_ui_node
var observation_ui_node
var crash : bool = false
var last_position : Vector2 = Vector2(0.0, 0.0)


################################################################################
### Signals

################################################################################
### Functions

func _ready():
	Reset()
	game_logic_node = get_node("/root/game/GameLogic")
	action_ui_node = get_node("/root/game/Overlay_UI_Action")
	observation_ui_node = get_node("/root/game/Overlay_UI_Observation")

func _physics_process(delta):
	if manual_control or received_step_command:
		received_step_command = false
		if not crash:
			GetAndCalcInput(delta)
			CalcDrivingForces()
			CalcKinematicModel()
			UpdateNodes()
			CalcStatistics()
		#todo: decide which method to clal depending on Server.gd setting
		#CalcSensors()
		#SenseReponse()
		CalcSensorGrid()
		SenseReponseGrid()
		ReportStatistics()
	else:
		# only update sensor measurement for UI / this is also needed so we can fetch a first measurement/initial state from here and pass to the Environment class in Python
		CalcSensorGrid()
		observation_ui_node.SetDistanceGrid(sensor_screenshot) # maybe this could be moved into CalcSensorGrid()
		self.update()

func WrapAngle(angle):
	if angle >= 0:
		return (fmod(angle+PI,2*PI) - PI)
	else:
		return (fmod(angle-PI,2*PI) + PI)

func _draw():
	DrawSensors()

func CalcStatistics():
	step_counter += 1.0
	var delta_movement = position - last_position
	distance_counter += delta_movement.length()
	last_position = position

func Step():
	#if step_counter%10 == 0:
	#	print("   Got Step command " + str(step_counter))
	received_step_command = true

func GetAndCalcInput(delta):
	if (manual_control):
		delta_step = delta
		GetAndCalcUserInput()
	else:
		delta_step = step_size
		GetExternalInput()
	action_ui_node.RotateWheel(steering)
	action_ui_node.SetThrottle(throttle)
	action_ui_node.SetBrake(brake)

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
	#print(steering)

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
	if velocity_longitudinal < 0:
		velocity_longitudinal = 0.0
	# todo: psi_dot, betao
	var beta : float = atan(l_r/(l_r+l_f) * tan(steering))
	var psi_dot : float = velocity_longitudinal/l_r * sin(beta)
	psi += psi_dot * delta_step * game_factor
	psi = WrapAngle(psi)
	x_dot = velocity_longitudinal * cos(psi+beta)
	y_dot = velocity_longitudinal * sin(psi+beta)

func UpdateNodes():
	var velocity : Vector2 = Vector2.ZERO
	velocity.x = x_dot * game_factor
	velocity.y = y_dot * game_factor
	#velocity = move_and_slide(velocity)
	var collision = move_and_collide(velocity * delta_step)
	crash = false
	if collision:
		crash = true
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

func CalcSensorGrid():
	var corner_rect = position - Vector2(42,42)
	var rect_around_car = Rect2(corner_rect,Vector2(84,84))
	sensor_screenshot = get_viewport().get_texture().get_data()
	sensor_screenshot.flip_y()
	sensor_screenshot = sensor_screenshot.get_rect(rect_around_car)
	#sensor_screenshot.save_png("C:\\work\\screenshot.png")

func DrawSensors():
	for idx in sensor_directions.size():
		var target = sensor_directions[idx] * sensor_readings[idx]
		self.draw_line(Vector2(0.0, 0.0), target/scale, Color(1, 0, 0, 1), 1.0, true) # this scene is scaled, so drawing must be scaled too

func SetId(_id):
	id = _id

func Reset():
	throttle = 0.0
	brake = 0.0
	steering = 0.0
	throttle_external = 0.0
	brake_external = 0.0
	steering_external = 0.0
	force_drive = 0.0
	velocity_longitudinal = 0.0
	x_dot = 0.0
	y_dot = 0.0
	psi = 0.0
	sensor_readings = [0.0, 0.0, 0.0, 0.0, 0.0]
	sensor_hits = [Vector2(0.0, 0.0), Vector2(0.0, 0.0), Vector2(0.0, 0.0), Vector2(0.0, 0.0), Vector2(0.0, 0.0)]
	crash = false
	step_counter = 0.0
	distance_counter = 0.0
	received_step_command = false
	last_position = position

func GetId():
	return id

func SetManualControl(val):
	manual_control = val

func GetManualControl():
	return manual_control

func Control(_throttle, _brake, _steering):
	throttle_external = _throttle
	brake_external = _brake
	steering_external = _steering

func Sense():
	SenseReponse()

func SenseGrid():
	SenseReponseGrid()

func SenseReponse():
	observation_ui_node.SetPsi(psi)
	observation_ui_node.SetDistance(sensor_readings[0], sensor_readings[1], sensor_readings[2], sensor_readings[3], sensor_readings[4])
	observation_ui_node.SetVelocity(velocity_longitudinal)
	if not manual_control:
		if game_logic_node:
			game_logic_node.SenseResponse(id, crash, sensor_readings[0], sensor_readings[1], sensor_readings[2], sensor_readings[3], sensor_readings[4], velocity_longitudinal, psi, position.x, position.y)

func SenseReponseGrid():
	observation_ui_node.SetPsi(psi)
	observation_ui_node.SetDistanceGrid(sensor_screenshot)
	observation_ui_node.SetVelocity(velocity_longitudinal)
	if not manual_control:
		if game_logic_node:
			game_logic_node.SenseResponseGrid(id, crash, sensor_screenshot, velocity_longitudinal, psi, position.x, position.y)

func ReportStatistics():
	if game_logic_node:
		game_logic_node.UpdateStatistics(distance_counter,step_counter)
