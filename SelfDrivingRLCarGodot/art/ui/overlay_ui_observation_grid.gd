extends Node2D

onready var psi_node = get_node("Background/Psi")
onready var grid_node = get_node("Background/Psi/grid")
onready var velocity_node = get_node("Background/Velocity")

# Called when the node enters the scene tree for the first time.
func _ready():
	var color = modulate
	color.a = 0.0
	set_modulate(color)

func SetPsi(psi):
	#psi_node.set_rotation(psi)
	pass

func SetDistanceGrid(sensor_readings_grid):
	grid_node.SetDistanceGrid(sensor_readings_grid)

func SetVelocity(v):
	velocity_node.value = v
