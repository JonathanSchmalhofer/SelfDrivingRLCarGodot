extends Node2D

onready var psi_node = get_node("Background/Psi")
onready var sensor0_node = get_node("Background/Psi/Sensor0")
onready var sensor1_node = get_node("Background/Psi/Sensor1")
onready var sensor2_node = get_node("Background/Psi/Sensor2")
onready var sensor3_node = get_node("Background/Psi/Sensor3")
onready var sensor4_node = get_node("Background/Psi/Sensor4")
onready var velocity_node = get_node("Background/Velocity")

# Called when the node enters the scene tree for the first time.
func _ready():
	var color = modulate
	color.a = 0.0
	set_modulate(color)

func SetPsi(psi):
	psi_node.set_rotation(psi)

func SetDistance(dist0, dist1, dist2, dist3, dist4):
	sensor0_node.value = dist0
	sensor1_node.value = dist1
	sensor2_node.value = dist2
	sensor3_node.value = dist3
	sensor4_node.value = dist4

func SetVelocity(v):
	velocity_node.value = v
