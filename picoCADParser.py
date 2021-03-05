"""
Made by Jordan Faas-Bush
@quickpocket on twitter

This is a script that will parse picoCAD save files and load them into a python class! It's pretty handy.
I'm also implementing a GUI wrapper for it so that people who don't want to run python can use it!




Current goal is to get the scale by 2 working -- I'm thinking the current problem is that it adds periods and zeros following floats even if they're actually ints?
I'm not sure though since that seems like something that would've been handled nicely...

But that's the current goal! Once I can export a new save I can start manipulating things and making a remapping system!

I've done that!

Todo:
tool for merging objects together via overlapping vertices!
	Consider trying to remove the hidden faces (if there are faces which are entirely made up of faces that will be merged then try removing it I guess?)

Tool for merging/unmerging the uvs of a mirrored face?
UI entry box for how to scale the uvs when generating them
UI entry box for which object to unwrap (so that you can scale them individually)

"""


# let's make some tools!

import os
import sys
import math
from PIL import Image, ImageDraw


colors = [
(0, 0, 0),
(29, 43, 83),
(126, 37, 83),
(0, 135, 81),
(171, 82, 54),
(95, 87, 79),
(194, 195, 199),
(255, 241, 232),
(255, 0, 77),
(255, 163, 0),
(255, 236, 39),
(0, 228, 54),
(41, 173, 255),
(131, 118, 156),
(255, 119, 168),
(255, 204, 170)
]



def make_128_UV_texture():
	img = Image.new("RGBA", (128, 128), 255)
	for y in range(128):
		for x in range(128):
			img.putpixel((x, y), (int(x/128.*255), int(y/128.*255), 0, 255))
	img.show()
	return img

def make_128_pico_palatte():
	img = Image.new("RGBA", (128, 128), 255)
	i = 1
	for y in range(128):
		for x in range(128):
			c = colors[i]
			i += 1
			i %= 16
			if i == 0:
				i += 1
			img.putpixel((x, y), tuple(c))
	img.show()
	return img

class PicoFace:
	def __init__(self, picoObject, vertexIndices, uvs, color = 0, doublesided = False, notshaded = False, priority = False, nottextured = False):
		self.obj = picoObject
		self.vertices = vertexIndices
		self.uvs = uvs
		self.doublesided = doublesided
		self.notshaded = notshaded
		self.priority = priority
		self.nottextured = nottextured
		self.color = color
		# print(self.is_coplanar(), self.get_normal().normalize(), self.color, [str(x) for x in self.uvs])
		# self.flatten_face()
		# self.get_scaled_projected_points_to_distance()
		# self.test_create_normals()
		self.dirty = False

	def __str__(self):
		t = "F: vertices: " + ", ".join([str(x) for x in self.vertices]) + ", uvs: " + ", ".join([str(x) for x in self.uvs]) + ",\t\tc=" + str(self.color)
		t += ", dbl: " + str(self.doublesided) + ", notshaded: " + str(self.notshaded) + ", priority: " + str(self.priority) + ", nottextured: " + str(self.nottextured)
		return t

	def __repr__(self):
		return str(self)

	def is_dirty(self):
		return self.dirty

	def mark_clean(self):
		self.dirty = False

	def output_save_text(self):
		# the text that'll get printed.
		o = "{"
		o += ",".join([str(x) for x in self.vertices])
		o += ", c=" + str(self.color)
		# dbl=1, noshade=1, notex=1, prio=1, 
		if self.doublesided:
			o += ", dbl=1"
		if self.notshaded:
			o += ", noshade=1"
		if self.nottextured:
			o += ", notex=1"
		if self.priority:
			o += ", prio=1"
		o += ", uv={"
		# now add the uvs!
		for uv in self.uvs:
			o += float_to_str(uv[0]) + "," + float_to_str(uv[1]) + ","
		o = o[:-1] + "} }"
		return o

	def get_num_edges(self):
		return len(self.vertices)

	def get_edge_vector(self, i):
		# return the vector between the vertices of that edge! Makes enough sense I think
		start = self.get_vertex_value(i % len(self.vertices))
		end = self.get_vertex_value((i + 1) % len(self.vertices))
		return end - start

	def flatten_face(self, basis_forgiveness = 0, center_points = False, use_edges_for_basis_fallback = True):
		# .2 is a decent basis forgiveness value I think...
		# this is for making the UV coords!
		# first find the first 2D axis!
		# figure out which edge is closest to a world axis!
		# if none of them are close to a world axis then I guess remap based on one of the axes?
		# if any of the world axes are 90 degrees from the normal then pick that?
		# otherwise see if any of the edges are flat-ish?
		# otherwise idk we'll figure it out :P
		normal = self.get_normal()
		if normal.magnitude() == 0:
			print("Couldn't find normal for face") # thus it's probably nothing? IDK how to handle this...
			normal = SimpleVector(1, 0, 0)
		normal = normal.normalize()
		# possible_basis = [[1, 0, 0], [0, 0, 1], [0, 1, 0]]
		possible_basis = [[0, 1, 0], [1, 0, 0], [0, 0, 1]] # best so far
		# possible_basis = [[0, 0, 1], [0, 1, 0], [1, 0, 0]]
		# possible_basis = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]# nope
		# possible_basis = [[0, 0, 1], [1, 0, 0], [0, 1, 0]]# nope
		# possible_basis = [[0, 1, 0], [0, 0, 1], [1, 0, 0]] # also possible, but equivalent to the other one

		a = [0, 0, 0]
		closest_nice_basis = [0, 0, 0]
		closest_value = 1000000000 # so this will get overwritten!
		for possible in possible_basis:
			# see what the dot product is -- is is 0? If so that's good because it's close to perpendicular to the normal!
			dot = abs(normal.dot(possible))
			if dot < closest_value:
				closest_nice_basis = possible
				closest_value = dot
			if dot <= basis_forgiveness:
				# then it's 90 degrees!
				a = possible
				closest_nice_basis = possible
				closest_value = dot
				break
		if a == [0, 0, 0]:
			# print("ERROR FINDING NICE BASIS OH DEAR...")
			# print("Best basis is " + str(closest_nice_basis), "with value of", closest_value)
			a = closest_nice_basis
			if (use_edges_for_basis_fallback):
				# then we're going to figure out which edge is closest to a world vector and use that!
				# abs of dot product of edge compared to the world vectors will get us what we want, the largest value is the most parallel to a world vector!
				closest_edge_value = -1
				closest_edge = None
				for i in range(len(self.vertices)):
					# check each of the edges!
					curr_edge = self.get_edge_vector(i)
					if curr_edge.magnitude() == 0:
						continue # can't check this edge it has zero length!
					curr_edge.normalize()
					for pb in possible_basis:
						# check each world direction to see what the dot is!
						d = abs(curr_edge.dot(pb))
						if d > closest_edge_value: # the larger the value the more in line with a world axis it is!
							closest_edge_value = d
							closest_edge = curr_edge
				# print("Found edge subsitute, val:", closest_edge_value, closest_edge)
				a = closest_edge
		a = SimpleVector(a).normalize()
		b = a.cross(normal).normalize()
		# print("Normal:", str(normal), "Basis: ", str(a), ", ", str(b))
		projected_points = []
		for i in range(len(self.vertices)):
			projected = self.get_vertex_value(i).project_onto_basis(a, b)
			projected_points.append(projected)
		# print("Projected values:", [str(x) for x in projected_points])
		if center_points:
			total = sum_list_of_simpleVectors(projected_points)
			average = total/len(projected_points)
			# print("total:", total, " average ", average)
			centered_points = [x-average for x in projected_points]
			# print("Centered:")
			# print(centered_points)
			return centered_points
		# otherwise return the projected ones
		return projected_points

		# total = sum_list_of_simpleVectors(projected_points)
		# average = total/len(projected_points)
		# # print("total:", total, " average ", average)
		# centered_points = [x-average for x in projected_points]
		# print(centered_points)
		# # need to round them to the nearest points!

	def flip_UVs(self):
		# flip the uv coords!
		for i in range(len(self.uvs)):
			temp = self.uvs[i].x
			self.uvs[i].x = self.uvs[i].y
			self.uvs[i].y = temp
		self.dirty = True

	def get_scaled_projected_points_to_distance(self, scalar = 1, basis_forgiveness = 0):
		# the projected points are the same order as the vertices, we can measure the distance between the first two vertices and the first two projected points
		# then scale it to match? That would make sense. They have to be centered though for it to scale correctly I think
		if len(self.vertices) < 2:
			print("Can't scale with only 1 vertex")
			return
		projected_points = self.flatten_face(basis_forgiveness = basis_forgiveness, center_points = True)
		projected_len = (projected_points[0] - projected_points[1]).magnitude()
		vertex_len = (self.get_vertex_value(0) - self.get_vertex_value(1)).magnitude()
		# print("prjoected", projected_len, vertex_len)
		if projected_len == 0:
			# this is mainly if you have faces that are entirely invisible
			projected_len = 1
			vertex_len = 0
		multiplier = scalar * (vertex_len / projected_len)
		# now scale up all the points by that?
		# I guess that works?
		scaled_points = [x * multiplier for x in projected_points]
		# print("Scaled points", scaled_points)
		return scaled_points

	def test_create_normals(self, scale = 2, flip_uvs = True):
		# probably need to pass in some way to determine how rotated this normal should be!
		scaled = self.get_scaled_projected_points_to_distance(scale)
		# scaled = self.flatten_face(basis_forgiveness = 0, center_points = True)
		minimum_value = minimum_values_in_list_of_simpleVectors(scaled)
		# print("min:", minimum_value)
		# scaled = [x + SimpleVector(5, 5, 5) for x in scaled]
		scaled = [x-minimum_value for x in scaled] # move it onto the uv image so it's positive!
		# scaled = [x.round_to_nearest(.25) for x in scaled]
		# scaled = [x.round_to_nearest(1) for x in scaled]
		# print("UVS:")
		# print(scaled)
		# print("")
		self.uvs = scaled
		if flip_uvs:
			self.flip_UVs() # by default flip the uvs!
		self.dirty = True

	def round_normals(self, nearest = .25):
		self.uvs = [x.round_to_nearest(nearest) for x in self.uvs]
		self.dirty = True

	def get_min_uv_coords(self):
		return minimum_values_in_list_of_simpleVectors(self.uvs)

	def get_max_uv_coords(self):
		return maximum_values_in_list_of_simpleVectors(self.uvs)

	def get_vertex_value(self, index):
		return self.obj.vertices[self.vertices[index]-1]

	def get_normal(self):
		# figure out the normal assuming it's planar!
		# for now just assume it's clockwise IDK?
		if (len(self.vertices) < 3):
			print("ERROR THERE AREN'T ENOUGH VERTICES OOPS")
			return SimpleVector(1, 0, 0)
		# need to loop over all the vertices to find three that are unique!
		vertices = []
		for i in range(len(self.vertices)):
			loc = self.get_vertex_value(i)
			if loc not in vertices:
				vertices.append(loc)
				if len(vertices) == 3:
					# calculate it!
					# a = self.get_vertex_value(vertices[0]) - self.get_vertex_value(vertices[1])
					# b = self.get_vertex_value(vertices[2]) - self.get_vertex_value(vertices[1])
					a = vertices[0] - vertices[1]
					b = vertices[2] - vertices[1]
					return b.cross(a) # I guess???? Is this right????? Hmmmmm?????
		print("ERROR THERE AREN'T ENOUGH UNIQUE VERTICES OOPS")
		return SimpleVector(1,0,0)

	def is_coplanar(self):
		# figure out if you're coplanar!
		if len(self.vertices) <= 3:
			return True # coplanar! Hopefully it won't have weird cases with only two vertices per face but well see what happens I guess...
		x1, y1, z1 = self.obj.vertices[self.vertices[0]-1]
		x2, y2, z2 = self.obj.vertices[self.vertices[1]-1]
		x3, y3, z3 = self.obj.vertices[self.vertices[2]-1]
		# print("PLANAR THING!: ", x1, y1, z1, x2, y2, z2, x3, y3, z3)
		for i in range(3, len(self.vertices)):
			# check to make sure it's actually coplanar!
			x, y, z = self.obj.vertices[self.vertices[i]-1]
			if not equation_plane(x1, y1, z1, x2, y2, z2, x3, y3, z3, x, y, z):
				return False
		return True
		# is_coplanar()


class PicoObject:
	def __init__(self, objText):
		# vertices
		# faces
		self.parse_base_info(objText)
		self.parse_vertices(objText)
		self.parse_faces(objText)
		# self.debug_print()
		# self.scale_up(2)
		self.dirty = False

	def scale_up(self, scalar):
		for i in range(len(self.vertices)):
			for j in range(len(self.vertices[i])):
				self.vertices[i][j] = self.vertices[i][j] * scalar

	def is_dirty(self):
		# return whether any faces are dirty!
		if self.dirty:
			return True
		for f in self.faces:
			if f.is_dirty():
				return True
		return False

	def mark_clean(self):
		self.dirty = False
		for f in self.faces:
			f.mark_clean()

	def parse_base_info(self, obj_text):
		start_index = obj_text.find("name='")
		name_text = obj_text[start_index:].strip("name='")
		close_index = name_text.find("'")
		self.name = name_text[:close_index]

		# parse pos
		postext = get_sub_table(obj_text, "pos=")[0]
		postext = postext[1:-1] # cut off the {}
		self.pos = [float(s) for s in postext.split(',')]

		# parse rot
		rottext = get_sub_table(obj_text, "rot=")[0]
		rottext = rottext[1:-1] # cut off the {}
		self.rot = [float(s) for s in rottext.split(',')]

	def parse_vertices(self, obj_text):
		verticestext = get_sub_table(obj_text, "v={")
		vertices = []
		for vtext in verticestext:
			trimmed = trim_front_until(vtext)
			coords = trimmed[1:-1].split(",")
			vertices += [SimpleVector([float(s) for s in coords])]
		self.vertices = vertices

	def parse_faces(self, obj_text):
		facestext = get_sub_table(obj_text, "f={")
		faces = []
		for ftext in facestext:
			trimmed = trim_front_until(ftext)
			# print(trimmed)
			uvs = get_sub_table(trimmed, "uv=")[0][1:-1].split(",")
			uvs = [float(x) for x in uvs]
			uvs_out = []
			for i in range(0, len(uvs), 2):
				uvs_out += [SimpleVector([uvs[i], uvs[i+1]])]
			uvs = uvs_out
			# print("UVS", uvs)

			# now get the vertex indices!
			# trimmed = trimmed[1:-1].split(',') # get rid of surrounding {}
			# trimmed = [x for x in trimmed if "=" not in x] # get rid of the uvs and the face settings and colors and whatever
			# print(trimmed)
			# coords = trimmed[1:-1].split(",")
			# faces += [[float(s) for s in coords]]
			trimmed = get_this_level_table(trimmed)
			vertices = [int(x) for x in trimmed.split(',') if "=" not in x]

			color_start = ftext.find("c=")
			color = 0
			if color_start != -1:
				# then we have a color!
				# it can be 0-15 hmmmm.
				color_text = ftext[color_start+2:color_start+4]
				try:
					color = int(color_text)
				except ValueError:
					color = int(color_text[0])

			doublesided = "dbl=1" in ftext
			notshaded = "noshade=1" in ftext
			priority = "prio=1" in ftext
			nottextured = "notex=1" in ftext
			faces += [PicoFace(self, vertices, uvs, color, doublesided, notshaded, priority, nottextured)]
		self.faces = faces

	def debug_print(self):
		t = "Object: name: " + str(self.name) + " pos: " + str(self.pos) + " rot: " + str(self.rot) + "\nVertices: " + str(self.vertices) + "\n"
		t += "\n".join([str(f) for f in self.faces])
		print(t)

	def output_save_text(self):
		o = "{\n name='" + self.name + "', pos={" + ",".join([float_to_str(x) for x in self.pos]) + "}, rot={" + ",".join([float_to_str(x) for x in self.rot]) +"},\n v={"
		# now add the vertex locations!
		for v in self.vertices:
			o += "\n  {" + ",".join([float_to_str(x) for x in v]) + "},"
		o = o[:-1] # remove the last comma
		o += "\n },\n f={"
		for f in self.faces:
			o += "\n  " + f.output_save_text() +","
		o = o[:-1] # remove the last comma!
		o += "\n } \n}"
		return o

class PicoSave:
	def __init__(self, filepath, original_text, objects):
		self.original_text = original_text
		self.objects = objects
		self.header = original_text.split("\n")[0] # the first line!
		self.footer = "%" + original_text.split("%")[1]
		self.dirty = False
		self.original_path = filepath

	def output_save_text(self, save_file_name):
		header = self.header.split(";")
		header = [header[0]] + [save_file_name] + header[2:]
		header = ";".join(header)
		o = header + "\n{"
		for obj in self.objects:
			o += "\n" + obj.output_save_text() + ","
		o = o[:-1] # get rid of last comma
		o += "\n}" + self.footer
		return o

	def pack_normals_naively(self, padding = .5, border = .5):
		self.dirty = True
		# this goes over the normals of every object and every face and just puts them next to each other! It's really naive so it won't work with too many faces
		faces = []
		for o in self.objects:
			for f in o.faces:
				faces.append(f)

		# now we have all the faces. Let's sort them by dimensions or something? Do I bother sorting them by size? Probably not!
		max_coords = SimpleVector(128/8, 120/8, 0)
		row_height = 0
		num_on_row = 0
		coords = SimpleVector(border, border, 0)
		for i in range(len(faces)):
			f = faces[i]
			min_uv = f.get_min_uv_coords()
			max_uv = f.get_max_uv_coords()
			dims = max_uv - min_uv
			# see if it fits in the current row, if not move to the next row!
			if dims.x > max_coords.x - (2*border) and num_on_row == 0:
				# if the object is too wide to fit then just stick it in on its own row, it's not going to fit anyways
				print("Warning: face UV too large to fit on texture")
				pass
			elif coords.x + dims.x >= max_coords.x - border:
				# then move it to the next row!
				coords.x = border
				coords.y += row_height + padding
				row_height = 0
				num_on_row = 0
			# now add it to the uv here!
			f.uvs = [x - min_uv + coords for x in f.uvs]

			# now remember the fact that we added it!
			row_height = max(row_height, dims.y)
			num_on_row += 1
			coords.x += dims.x + padding # move it horizontally!
		if coords.y + row_height > max_coords.y:
			print("Warning: UVs too large vertically to fit on texture")

	def pack_normals_largest_first(self, padding = .5, border = .5):
		# basically steal the code from pack naive just prioritize the largest items first! That way it should be better at fitting things? Maybe??? not sure.
		self.dirty = True
		# this goes over the normals of every object and every face and just puts them next to each other! It's really naive so it won't work with too many faces
		faces = []
		for o in self.objects:
			for f in o.faces:
				faces.append(f)

		# now we have all the faces. Let's sort them by dimensions or something? Do I bother sorting them by size? Probably not!
		finished_faces = []
		max_coords = SimpleVector(128/8, 128/8, 0)
		row_height = 0
		num_on_row = 0
		coords = SimpleVector(border, border, 0)
		for i in range(len(faces)):
			f = None
			largest_face = None
			largest_dims = SimpleVector(-1, -1, 0)
			# find the largest face vertically that isn't finished already!
			for j in range(len(faces)):
				f = faces[j]
				if f in finished_faces:
					continue # it's already been placed!
				min_uv = f.get_min_uv_coords()
				max_uv = f.get_max_uv_coords()
				dims = max_uv - min_uv
				if dims.y > largest_dims.y:
					largest_dims = dims
					largest_face = f

			# now we have the largest face! Let's place it into the image!
			f = largest_face
			dims = largest_dims
			min_uv = f.get_min_uv_coords()
			max_uv = f.get_max_uv_coords()
			finished_faces.append(f)

			# see if it fits in the current row, if not move to the next row!
			if dims.x > max_coords.x - (2*border) and num_on_row == 0:
				# if the object is too wide to fit then just stick it in on its own row, it's not going to fit anyways
				print("Warning: face UV too large to fit on texture")
				pass
			elif coords.x + dims.x >= max_coords.x - border:
				# then move it to the next row!
				coords.x = border
				coords.y += row_height + padding
				row_height = 0
				num_on_row = 0
			# now add it to the uv here!
			f.uvs = [x - min_uv + coords for x in f.uvs]

			# now remember the fact that we added it!
			row_height = max(row_height, dims.y)
			num_on_row += 1
			coords.x += dims.x + padding # move it horizontally!
		if coords.y + row_height > max_coords.y:
			print("Warning: UVs too large vertically to fit on texture")

	def save_to_file(self, filepath):
		ofile = open(filepath, "w")
		filename = os.path.splitext(os.path.basename(filepath))[0] # get the name to put into the picoCAD Save!
		ofile.write(self.output_save_text(filename))

	def is_dirty(self):
		# check whether any of the objects are dirty!
		return self.dirty or len([x for x in self.objects if x.is_dirty()]) > 0

	def mark_clean(self):
		self.dirty = False
		for o in self.objects:
			o.mark_clean()

	def export_texture(self):
		img = Image.new("RGBA", (128, 128), (255, 255, 255))
		img_string = self.footer[1:] # remove the % sign
		y = 0
		for line in img_string.split("\n"):
			line = line.strip()
			if len(line) != 128:
				# print("Error line is too short!: '" + str(line) + "'")
				continue
			for x in range(len(line)):
				c = line[x]
				i = "0123456789abcdef".find(c)
				if i == -1:
					print("Couldn't find color for: '" + str(c) + "'")
					continue
				color = colors[i]
				img.putpixel((x, y), color)
			y += 1
		return img

	def make_UV_image(self, scale = 1, color_by_face = False):
		pixelScale = 8 * scale # default picoCAD is 8, can this be changed? no clue, so putting this here
		# you can now pass in a scalar so that if you wanted a larger texture like a 512x512 texture (so that you can make the textures more detailed) you can!
		img = Image.new("RGBA", (int(128 * scale), int(128 * scale)), (255, 255, 255))
		draw = ImageDraw.Draw(img)
		for obj in self.objects:
			for face in obj.faces:
				# now draw the uvs!
				c = (0, 0, 0, 255)
				if color_by_face:
					c = colors[face.color]
				for i in range(len(face.uvs)):
					# draw a line between the UVs!
					a = face.uvs[i]
					b = face.uvs[(i+1) % len(face.uvs)]
					draw.line((int(a.x*pixelScale), int(a.y*pixelScale), int(b.x*pixelScale), int(b.y*pixelScale)), c)
		# img.save(uv_image_output_file, "png")
		return img

class SimpleVector:
	def __init__(self, x_or_list, y = 0, z = 0):
		# pass in coords!
		# print(type(x_or_list), type(x_or_list) == list, x_or_list)
		if type(x_or_list) == list:
			self.x = 0
			self.y = 0
			self.z = 0
			if len(x_or_list) >=  1:
				self.x = x_or_list[0]
			if len(x_or_list) >=  2:
				self.y = x_or_list[1]
			if len(x_or_list) >=  3:
				self.z = x_or_list[2]
		elif (type(x_or_list)) == SimpleVector:
			self.x = x_or_list.x
			self.y = x_or_list.y
			self.z = x_or_list.z
		else:
			# we're using regular coords!
			self.x = x_or_list
			self.y = y
			self.z = z

	def magnitude(self):
		return math.sqrt(self.x*self.x + self.y*self.y + self.z*self.z)

	def copy(self):
		return SimpleVector(self.x, self.y, self.z)

	def normalize(self):
		return self.copy() / self.magnitude()

	def __eq__(self, other):
		return self.x == other[0] and self.y == other[1] and self.z == other[2]

	def __add__(self, other):
		x = self.x + other[0]
		y = self.y + other[1]
		z = self.z + other[2]
		return SimpleVector(x, y, z)

	def __sub__(self, other):
		x = self.x - other[0]
		y = self.y - other[1]
		z = self.z - other[2]
		return SimpleVector(x, y, z)

	def __truediv__(self, scalar):
		# can only divide by a scalar
		x = self.x / scalar
		y = self.y / scalar
		z = self.z / scalar
		return SimpleVector(x, y, z)

	def __mul__(self, scalar):
		# can only multiply by a scalar
		x = self.x * scalar
		y = self.y * scalar
		z = self.z * scalar
		return SimpleVector(x, y, z)

	def round_to_nearest(self, nearest):
		return SimpleVector(round(self.x / nearest)*nearest, round(self.y/nearest)*nearest, round(self.z/nearest)*nearest)

	def dot(self, other):
		return self.x*other[0] + self.y*other[1] + self.z*other[2]

	def cross(self, other):
		x = self.y*other[2] - self.z*other[1]
		y = self.z*other[0] - self.x*other[2]
		z = self.x*other[1] - self.y*other[0]
		return SimpleVector(x, y, z)

	def project_onto_basis(self, u, v):
		# project this value onto the new basis and return that!
		return SimpleVector(self.dot(u), self.dot(v))

	def __getitem__(self, index):
		if index == 0:
			return self.x
		if index == 1:
			return self.y
		if index == 2:
			return self.z
		# print("ERROR SHOUlDN'T BE ABLE TO INDEX THIS FAR OOPS")
		raise IndexError

	def __delitem__(self, index):
		if index == 0:
			self.x = 0
		elif index == 1:
			self.y = 0
		elif index == 2:
			self.z = 0
		else:
			raise IndexError

	def __len__(self):
		return 3 # it's always 3!

	def __iter__(self):
		class SimpleVectorIter:
			def __init__(iterself, v):
				iterself.vector = v
				iterself.i = 0

			def __next__(iterself):
				if iterself.i >= 3:
					raise StopIteration
				o = iterself.vector[iterself.i]
				iterself.i += 1
				return o
		return SimpleVectorIter(self)

	def __setitem__(self, index, value):
		if index == 0:
			self.x = value
		elif index == 1:
			self.y = value
		elif index == 2:
			self.z = value
		else:
			raise IndexError
			# print("ERROR SHOULDN'T SET INDEX THIS FAR OOPS")
			# return

	def __str__(self):
		return "<"+str(self.x) + ","+str(self.y)+","+str(self.z)+">"

	def __repr__(self):
		return str(self)

def save_image(img, filepath):
	img.save(filepath, ".png")

def sum_list_of_simpleVectors(list_of_simpleVectors):
	t = SimpleVector(0,0,0)
	for v in list_of_simpleVectors:
		t += v
	return t

def minimum_values_in_list_of_simpleVectors(list_of_simpleVectors):
	t = list_of_simpleVectors[0].copy()
	for v in list_of_simpleVectors:
		t.x = min(t.x, v.x)
		t.y = min(t.y, v.y)
		t.z = min(t.z, v.z)
	return t

def maximum_values_in_list_of_simpleVectors(list_of_simpleVectors):
	t = list_of_simpleVectors[0].copy()
	for v in list_of_simpleVectors:
		t.x = max(t.x, v.x)
		t.y = max(t.y, v.y)
		t.z = max(t.z, v.z)
	return t

def load_picoCAD_save(filepath):
	if os.path.exists(filepath):
		# print("it's real!")
		f = open(filepath, "r")
		text = f.read()
		# print(text)
		first_line = text.split("\n")[0]
		if "picocad" not in first_line:
			return None, False
		json_text = text[text.index("{"):text.rindex("}")+1] # cut out the text at the beginning and the sprite sheet at the end!
		if len(json_text) == 0:
			return None, False
		# print(json_text)
		# json_text = json_text.replace("'", '"')
		# json_text = json_text.replace("=", ':')
		# print(json_text)
		# return ""
		objects = parse_picoCAD_objects(json_text)
		if len(objects) == 0:
			# arguably it could be valid? Hmmmmm.
			return None, False
		s = PicoSave(filepath, text, objects)
		# output = s.output_save_text()
		# print("\n\n\nOUTPUT:")
		# print(output)
		# for i in range(len(output)):
		# 	if output[i] != text[i]:
		# 		print(output[i:])
		# 		break
		# print(output == text)
		return s, True
	else:
		print("Error: file", filepath, "does not exist!")
		return None, False

def float_to_str(f):
	if int(f) == f:
		return str(int(f))
	return str(f)


def parse_picoCAD_objects(json_text):
	# turns out the pico save isn't nice json because it's used in lua, so everything's a table...
	# guess we'll have to figure out how to parse it nicely!
	objects = []
	# print("Json text", json_text)
	# print("here done")
	objects = get_sub_table(json_text, trim_outside = True)
	objects = ["{" + x + "}" for x in objects]
	# [print(type(x)) for x in objects]
	# objects = [get_sub_table(x, debug_print = False) for x in objects]
	output = []
	for obj in objects:
		# print("parsing new object:")
		# get_sub_table(obj, "pos:{")
		# name = get_sub_table(obj, "name:", indent = '"', outdent = '"')
		# print("name:", name)
		picoObj = PicoObject(obj)
		output += [picoObj]
	return output

def trim_front_until(text):
	# converts ", \n {lajsdfljk}" into "{lajsdfljk}"
	start = text.find("{")
	if start == -1:
		start = 0
	return text[start:]

def get_sub_table(table, startingtext = "", indent="{", outdent="}", find_one=False, debug_print = False, trim_outside = False):
	# look through this table "{}" and return a list of sub-table strings!
	table = table.strip()
	if table[0] != "{" or table[-1] != "}":
		print("Oh dear we have an error parsing the tables, this isn't a nice table:", table)
		return []
	if trim_outside:
		table = table[1:-1].strip()
	# table = table[1:-1] # cut off the beginning and end!
	sub = []
	indentation = 0
	current_sub = ""
	if debug_print:
		print(table)
	start = 0
	if (len(startingtext) > 0):
		# then find where to start!
		start = table.find(startingtext)
		if (start == -1):
			print("Error: couldn't find starting text:", startingtext)
			return []
		start += len(startingtext)
	for i in range(start, len(table)):
		c = table[i]
		current_sub += c
		if c == indent: # by default {
			indentation += 1
		elif c == outdent: # by default }
			indentation -= 1
			# if debug_print:
			# 	print("Deindent", indentation, current_sub)
			if indentation < 0:
				break
			if indentation == 0:
				# then we've finished another table!
				sub += [current_sub]
				if debug_print:
					print("here", current_sub)
				current_sub = ""
				if len(startingtext) > 0 and find_one:
					# then return now we've found the table!
					break
	# if debug_print:
	# 	print("HERE@", current_sub, indentation)

	if len(current_sub) > 0 and indentation == 0:
		sub += [current_sub]
		# print(sub)
	# print(len(sub))
	return sub

def get_this_level_table(table, startingtext = "", indent="{", outdent="}"):
	# look through this table "{}" and return a list of sub-table strings!
	table = table.strip()
	if table[0] != "{" or table[-1] != "}":
		print("Oh dear we have an error parsing the tables, this isn't a nice table:", table)
		return []
	table = table[1:-1] # cut off the beginning and end!
	sub = ""
	indentation = 0
	start = 0
	if (len(startingtext) > 0):
		# then find where to start!
		start = table.find(startingtext)
		if (start == -1):
			print("Error: couldn't find starting text:", startingtext)
			return []
		start += len(startingtext)
	for i in range(start, len(table)):
		c = table[i]
		if c == indent: # by default {
			indentation += 1
		elif c == outdent: # by default }
			indentation -= 1
		if indentation == 0:
			sub += c

	return sub


def equation_plane(x1, y1, z1, x2, y2, z2, x3, y3, z3, x, y, z):
	# https://www.geeksforgeeks.org/program-to-check-whether-4-points-in-a-3-d-plane-are-coplanar/
	a1 = x2 - x1 
	b1 = y2 - y1 
	c1 = z2 - z1 
	a2 = x3 - x1 
	b2 = y3 - y1 
	c2 = z3 - z1 
	a = b1 * c2 - b2 * c1 
	b = a2 * c1 - a1 * c2 
	c = a1 * b2 - b1 * a2 
	d = (- a * x1 - b * y1 - c * z1) 
	
	# equation of plane is: a*x + b*y + c*z = 0 # 
	
	# checking if the 4th point satisfies 
	# the above equation 
	return a * x + b * y + c * z + d == 0


# if __name__ == "__main__":
	# test stuff!
	# test = [[1,2,3], {"a":"hello"}]

	# make_128_pico_palatte()

	# save, valid = load_picoCAD_save(save_to_load)
	# if (save == None):
	# 	sys.exit(1)
	# ofile = open(output_file, "w")
	# filename = os.path.splitext(os.path.basename(output_file))[0]
	# # print(filename)
	# ofile.write(save.output_save_text(filename))

	# save.export_texture().show()
	# save.make_UV_image().show()

	# make_UV_image(save).show()