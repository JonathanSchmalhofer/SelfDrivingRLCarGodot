extends Node2D

onready var grid_node = get_node("grid")

var sensor_screenshot : Image
const top_left = Vector2(0, 0)
const rows : int = 84

func SetDistanceGrid(sensor_screenshot : Image):
	SetShaderParam(sensor_screenshot)

func SetShaderParam(sensor_screenshot):
	# Source: https://www.gitmemory.com/issue/godotengine/godot/10751/480585584
	#
	# The array I want to send to my shader
	#var array = [1, 1, 1, 0, 2, 2, 2, 0, 0, 3]

	# You'll have to get thoose the way you want
	#var array_width = 84
	#var array_heigh = 84

	# The following is used to convert the array into a Texture
	#var byte_array = PoolByteArray(sensor_readings_grid)
	#var img = Image.new()

	# I don't want any mipmaps generated : use_mipmaps = false
	# I'm only interested with 1 component per pixel (the corresponding array value) : Format = Image.FORMAT_R8
	#img.create_from_data(array_width, array_heigh, false, Image.FORMAT_R8, byte_array)

	var texture = ImageTexture.new()

	# Override the default flag with 0 since I don't want texture repeat/filtering/mipmaps/etc
	texture.create_from_image(sensor_screenshot, 0)

	# Upload the texture to my shader
	grid_node.get_material().set_shader_param("grid", texture)
	

