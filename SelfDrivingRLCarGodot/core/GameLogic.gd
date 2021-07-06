extends Node

const CAR = preload("res://core/car/Car.tscn")
const UUID = preload("res://core/uuid.gd")

var server_node
var car_node

var score_label
var distance_label
var step_label

var max_score : float = 0.0
var max_distance : float = 0.0
var max_steps : float = 0.0
var endless_mode : bool = false

const pos_init : Vector2 = Vector2(630, 280)
const rot_init : float = 0.0
const scale : float = 0.4
const weight_distance : float = 1.0
const weight_steps : float = 1.0

# Called when the node enters the scene tree for the first time.
func _ready():
	server_node = get_node("/root/game/Server")
	score_label = get_node("/root/game/Labels/MaxScoreLabel")
	distance_label = get_node("/root/game/Labels/MaxDistanceLabel")
	step_label = get_node("/root/game/Labels/MaxStepsLabel")
	ResetStatistics()
	UpdateLabels()

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta):
	car_node = get_node("/root/game/Car")
	if Input.is_action_pressed("ui_cancel"):
		DeleteAllCars()
	if Input.is_action_pressed("ui_select"):
		DeleteAllCars()
		if (car_node):
			car_node.add_child(CreateCar(UUID.v4(), true))
	UpdateLabels()

func SetEndlessMode(mode):
	endless_mode = mode

func ResetStatistics():
	max_score = 0.0
	max_distance = 0.0
	max_steps = 0.0

func UpdateLabels():
	if (score_label):
		score_label.text = str("%10.2f" % max_score)
	if (distance_label):
		distance_label.text = str("%10.2f" % max_distance)
	if (step_label):
		step_label.text = str("%10.2f" % max_steps)

func DeleteAllCars():
	ResetStatistics()
	if (car_node):
		for child in car_node.get_children():
			car_node.remove_child(child)

func DeleteCar(uuid):
	if (car_node):
		for child in car_node.get_children():
			if child.GetId() == uuid:
				car_node.remove_child(child)
				print("Deleting " + str(uuid))
				break

func CreateCar(uuid, manual_control):
	ResetStatistics()
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

func SenseGrid(uuid):
	if (car_node):
		for child in car_node.get_children():
			if child.GetId() == uuid:
				child.SenseGrid()

func Reset(uuid):
	if (car_node):
		for child in car_node.get_children():
			if child.GetId() == uuid:
				child.transform = Transform2D(rot_init, pos_init)				
				child.scale = Vector2(scale, scale)
				child.Reset()

func StepAll():
	if (car_node):
		for child in car_node.get_children():
			child.Step()
	UpdateLabels()

func Step(uuid):
	if (car_node):
		for child in car_node.get_children():
			if child.GetId() == uuid:
				child.Step()
	UpdateLabels()

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

func DiscreteControl(uuid, action):
	if (car_node):
		for child in car_node.get_children():
			if child.GetId() == uuid:
				child.DiscreteControl(action)

func SenseResponse(uuid, crash, sensor_0, sensor_1, sensor_2, sensor_3, sensor_4, velocity, yaw, pos_x, pos_y):
	if server_node:
		var send_score : float
		if endless_mode:
			send_score = 0.0 # the score will be reported as 0, thus the Gym Environment will not cancel
		else:
			send_score = max_score
		server_node.SenseResponse(uuid, send_score, crash, sensor_0, sensor_1, sensor_2, sensor_3, sensor_4, velocity, yaw, pos_x, pos_y)

func SenseResponseGrid(uuid, crash, sensor_screenshot : Image, velocity, yaw, pos_x, pos_y):
	if server_node:
		var send_score : float
		if endless_mode:
			send_score = 0.0 # the score will be reported as 0, thus the Gym Environment will not cancel
		else:
			send_score = max_score
		server_node.SenseResponseGrid(uuid, send_score, crash, sensor_screenshot, velocity, yaw, pos_x, pos_y)

func UpdateStatistics(distance, steps):
	if distance > max_distance or steps > max_steps:
		max_distance = distance
		max_steps = steps
	max_score = (weight_distance * max_distance) - (weight_steps * max_steps)
