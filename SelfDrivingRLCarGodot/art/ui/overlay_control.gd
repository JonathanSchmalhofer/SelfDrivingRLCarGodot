extends Node2D

onready var action_checkbox = get_node("Action")
onready var observation_checkbox = get_node("Observation")

var overlay_action_node
var overlay_observation_node

func _ready():
	action_checkbox.connect("pressed", self, "_action_checkbox_pressed")
	observation_checkbox.connect("pressed", self, "_observation_checkbox_pressed")
	overlay_action_node = get_node("/root/game/Overlay_UI_Action")
	overlay_observation_node = get_node("/root/game/Overlay_UI_Observation")

func _action_checkbox_pressed():
	if action_checkbox.pressed:
		var color = overlay_action_node.modulate
		color.a = 0.75
		overlay_action_node.set_modulate(color)
	else:
		var color = overlay_action_node.modulate
		color.a = 0.0
		overlay_action_node.set_modulate(color)

func _observation_checkbox_pressed():
	if observation_checkbox.pressed:
		var color = overlay_observation_node.modulate
		color.a = 0.75
		overlay_observation_node.set_modulate(color)
	else:
		var color = overlay_observation_node.modulate
		color.a = 0.0
		overlay_observation_node.set_modulate(color)
