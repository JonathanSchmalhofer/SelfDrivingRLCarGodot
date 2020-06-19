extends Node

const UUID = preload("res://core/uuid.gd")

const buffer_size : int = 1024
const header_size : int = 6

var server
var tcp_stream_dict : Dictionary
var tcp_back_stream_dict : Dictionary
var buffer_dict : Dictionary
var msg_size_dict : Dictionary
var control_counter : int = 0

var game_logic_node

# Called when the node enters the scene tree for the first time.
func _ready():
	server = TCP_Server.new()
	server.listen(42424, "*")
	game_logic_node = get_node("/root/Node2D/GameLogic")

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta):
	if server.is_listening():
		if server.is_connection_available():
			#print("Connection available")
			var tcp_stream = server.take_connection()
			tcp_stream.set_no_delay(true)
			var uuid = UUID.v4()
			tcp_stream_dict[uuid] = tcp_stream
			buffer_dict[uuid] = PoolByteArray()
			msg_size_dict[uuid] = int(0)
	if tcp_stream_dict.size() > 0:
		CollectData()
		ParseData()

func CollectData():	
	for key in tcp_stream_dict:
		if tcp_stream_dict[key].get_available_bytes() >= header_size:
			# first get the header of the message, to see how many bytes we need to read (depends on the command)
			var body_size : int = 0
			var header_data = tcp_stream_dict[key].get_data(header_size)
			if not header_data[1].get_string_from_utf8() == "(HEAD:":
				print("Invalid Header Data at key = " + String(key) + ". Expected (HEAD:, got: " + header_data[1].get_string_from_utf8())
				CloseConnection(key)
			else:
				var next_char = ""
				var remaining_attempts = 4 # number of bytes expected to come
				var size_data = PoolByteArray()
				while tcp_stream_dict[key].get_available_bytes() > 0 and remaining_attempts > 0:
					var return_data = tcp_stream_dict[key].get_data(1) # get char by char
					var error = return_data[0]
					var data = return_data[1]
					next_char = data.get_string_from_utf8()
					remaining_attempts -= 1
					if next_char == ")":
						break
					else:
						size_data.append_array(data)
				body_size = int(size_data.get_string_from_utf8())
				msg_size_dict[key] = body_size
				#print("HEAD received")
			# Now we know, how big the body of the message will be
			if body_size > 0:
				var remaining_buffer = buffer_size - buffer_dict[key].size()
				var expected_data = body_size
				while tcp_stream_dict[key].get_available_bytes() > 0 and remaining_buffer > 0 and expected_data > 0:
					var current_buffer = buffer_dict[key]
					var readable_bytes = min(remaining_buffer, tcp_stream_dict[key].get_available_bytes())
					readable_bytes = min(readable_bytes, body_size)
					var return_data = tcp_stream_dict[key].get_data(readable_bytes)
					var _error = return_data[0]
					var data = return_data[1]
					current_buffer.append_array(data)
					buffer_dict[key] = current_buffer
					remaining_buffer -= data.size()
					expected_data -= data.size()
				#print("BODY received")

func ParseData():
	for key in buffer_dict:
		if not buffer_dict[key].empty():
			var message = buffer_dict[key].subarray(0, msg_size_dict[key]-1)
			buffer_dict[key] = buffer_dict[key].subarray(msg_size_dict[key], buffer_dict[key].size()-1)
			msg_size_dict[key] = 0
			#print("idx = " + String(idx) + ": " + message.get_string_from_utf8())
			match message.get_string_from_utf8():
				"(REGISTER)":
					RegisterCommand(key)
				"(RESET)":
					ResetCommand(key)
				"(SENSE)":
					SenseCommand(key)
				"(CLOSE)":
					CloseCommand(key)
				var command_with_args:
					HandleCommandWithArguments(key, command_with_args)

func CloseConnection(key):
	tcp_stream_dict[key].disconnect_from_host()
	tcp_stream_dict.erase(key)
	buffer_dict.erase(key)
	msg_size_dict.erase(key)

func RegisterCommand(key):
	if game_logic_node:
		game_logic_node.Register(key)
	

func ResetCommand(key):
	if game_logic_node:
		game_logic_node.Reset(key)

func SenseCommand(key):
	if game_logic_node:
		game_logic_node.Sense(key)

func CloseCommand(key):
	CloseConnection(key)
	if game_logic_node:
		game_logic_node.Close(key)

func HandleCommandWithArguments(key, command):
	if HandleControlCommand(key, command):
		return

func HandleControlCommand(key, command):
	var regex = RegEx.new()
	regex.compile("(?:\\(CONTROL:)(?<throttle>[+-]?\\d*\\.?\\d*);(?<brake>[+-]?\\d*\\.?\\d*);(?<steering>[+-]?\\d*\\.?\\d*)")
	var result = regex.search(command)
	if result:
		if not result.get_string("throttle").empty() and not result.get_string("brake").empty() and not result.get_string("steering").empty():
			var throttle : float = float(result.get_string("throttle"))
			var brake : float = float(result.get_string("brake"))
			var steering : float = float(result.get_string("steering"))
			if game_logic_node:
				game_logic_node.Control(key, throttle, brake, steering)
			control_counter += 1
			if control_counter >= tcp_stream_dict.size():
				if game_logic_node:
					game_logic_node.Step()
			return true
	return false

func SenseResponse(uuid, sensor_0, sensor_1, sensor_2, sensor_3, sensor_4, velocity, yaw, pos_x, pos_y):
	if tcp_stream_dict[uuid]:
		if tcp_stream_dict[uuid].is_connected_to_host():
			var response : String = String(sensor_0) + ";" + String(sensor_1) + ";" + String(sensor_2) + ";" + String(sensor_3) + ";" + String(sensor_4) + ";" + String(velocity) + ";" + String(yaw) + ";" + String(pos_x) + ";" + String(pos_y)
			var retval = tcp_stream_dict[uuid].put_partial_data(response.to_ascii())
			if retval[0]:
				print(String(uuid) + "Error: " + String(retval[0]))
				print(String(uuid) + "Data: " + String(retval[1]))

func RegisterResponse(uuid):
	if tcp_stream_dict[uuid]:
		if tcp_stream_dict[uuid].is_connected_to_host():
			var response : String = String(uuid)
			var retval = tcp_stream_dict[uuid].put_partial_data(response.to_ascii())
			if retval[0]:
				print(String(uuid) + "Error: " + String(retval[0]))
				print(String(uuid) + "Data: " + String(retval[1]))
