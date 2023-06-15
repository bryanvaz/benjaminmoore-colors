# method to convert RGB int values to hex
def rgb_to_hex(rgb):
    return f"#{rgb['r']:02x}{rgb['g']:02x}{rgb['b']:02x}"

# convert rgb floats to rgb ints
def rgb_float_to_int(rgb):
    return { "r": int(rgb[0]*255), "g": int(rgb[1]*255), "b": int(rgb[2]*255), }
