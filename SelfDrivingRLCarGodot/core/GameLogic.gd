extends Node

const CAR = preload("res://core/car/Car.tscn")
const UUID = preload("res://core/uuid.gd")

var server_node
var car_node

const pos_init : Vector2 = Vector2(630, 280)
const rot_init : float = 0.0
const scale : float = 0.4

signal sense_reponse_to_server(uuid, sensor_0, sensor_1, sensor_2, sensor_3, sensor_4, velocity, yaw, pos_x, pos_y)

# Called when the node enters the scene tree for the first time.
func _ready():
	server_node = get_node("/root/Node2D/Server")
	server_node.connect("command_close", self, "_on_command_close")
	server_node.connect("command_register", self, "_on_command_register")
	server_node.connect("command_control", self, "_on_command_control")


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta):
	car_node = get_node("/root/Node2D/Car")
	if Input.is_action_pressed("ui_cancel"):
		DeleteAllCars()
	if Input.is_action_pressed("ui_select"):
		DeleteAllCars()
		if (car_node):
			car_node.add_child(CreateCar(UUID.v4(), true))

func DeleteAllCars():
	if (car_node):
		for child in car_node.get_children():
			car_node.remove_child(child)

func DeleteCar(uuid):
	if (car_node):
		for child in car_node.get_children():
			if child.GetId() == uuid:
				car_node.remove_child(child)
				#print("Remove car " + String(uuid))
				break

func CreateCar(uuid, manual_control):
	var new_car = CAR.instance()
	new_car.SetId(uuid)
	new_car.transform = Transform2D(rot_init, pos_init)
	new_car.scale = Vector2(scale, scale)
	new_car.SetManualControl(manual_control)
	#print("Create car " + String(uuid))
	return new_car

func _on_command_close(uuid):
	#print("Received close for uuid: " + String(uuid))
	DeleteCar(uuid)

func _on_command_register(uuid):
	if (car_node):
		car_node.add_child(CreateCar(uuid, false))
		for child in car_node.get_children():
			if child.GetId() == uuid:
				child.connect("sense_response", self, "_on_sense_response")

func _on_command_control(uuid, throttle, brake, steering):
	if (car_node):
		for child in car_node.get_children():
			if child.GetId() == uuid:
				child.SetExternalInputs(throttle, brake, steering)
				break

func _on_sense_response(uuid, sensor_0, sensor_1, sensor_2, sensor_3, sensor_4, velocity, yaw, pos_x, pos_y):
	emit_signal("sense_reponse_to_server", uuid, sensor_0, sensor_1, sensor_2, sensor_3, sensor_4, velocity, yaw, pos_x, pos_y)
