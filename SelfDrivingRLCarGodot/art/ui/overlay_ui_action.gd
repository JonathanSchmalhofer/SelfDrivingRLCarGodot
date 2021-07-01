extends Node2D

onready var wheel_node = get_node("Background/Wheel")
onready var throttle_node = get_node("Background/Throttle")
onready var brake_node = get_node("Background/Brake")


# Called when the node enters the scene tree for the first time.
func _ready():
	var color = modulate
	color.a = 0.0
	set_modulate(color)
	throttle_node.value = 0
	brake_node.value = 0

func RotateWheel(angle):
	wheel_node.set_rotation(angle)

func SetThrottle(throttle):
	throttle_node.value = throttle * 100

func SetBrake(brake):
	brake_node.value = brake * 100
