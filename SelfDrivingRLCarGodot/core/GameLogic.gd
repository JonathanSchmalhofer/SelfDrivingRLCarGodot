extends Node

const CAR = preload("res://core/car/Car.tscn")
const UUID = preload("res://core/uuid.gd")

var server_node
var car_node

const pos_init : Vector2 = Vector2(630, 280)
const rot_init : float = 0.0
const scale : float = 0.4

# Called when the node enters the scene tree for the first time.
func _ready():
	server_node = get_node("/root/Node2D/Server")

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
				break

func CreateCar(uuid, manual_control):
	var new_car = CAR.instance()
	new_car.SetId(uuid)
	new_car.transform = Transform2D(rot_init, pos_init)
	new_car.scale = Vector2(scale, scale)
	new_car.SetManualControl(manual_control)
	return new_car

func Sense(uuid):
	if (car_node):
		for child in car_node.get_children():
			if child.GetId() == uuid:
				child.Sense()

func Reset(uuid):
	if (car_node):
		for child in car_node.get_children():
			if child.GetId() == uuid:
				child.Reset()

func Step():
	if (car_node):
		for child in car_node.get_children():
			child.Step()

func Close(uuid):
	DeleteCar(uuid)

func Register(uuid):
	if (car_node):
		car_node.add_child(CreateCar(uuid, false))
		for child in car_node.get_children():
			if child.GetId() == uuid:
				if server_node:
					server_node.RegisterResponse(uuid)
		

func Control(uuid, throttle, brake, steering):
	if (car_node):
		for child in car_node.get_children():
			if child.GetId() == uuid:
				child.Control(throttle, brake, steering)

func SenseResponse(uuid, sensor_0, sensor_1, sensor_2, sensor_3, sensor_4, velocity, yaw, pos_x, pos_y):
	if server_node:
		server_node.SenseResponse(uuid, sensor_0, sensor_1, sensor_2, sensor_3, sensor_4, velocity, yaw, pos_x, pos_y)
