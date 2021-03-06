"""
# Format text elements into text images.

# Paragraph level formatting functions usually return &Fragment while section-level
# returns &Image.

# &chapter and &elements are the primary entry points where chapter takes a single
# (element/type)`chapter` node and elements takes a sequence of arbitrary nodes.

# [ Types ]

# /Fragment/
	# A string without newlines.
# /Line/
	# A sequence of &Fragment instances.
# /Image/
	# An iterator producing &Line instances.
"""
import typing
from . import types
from . import document

Fragment = str
Line = typing.Sequence[Fragment]
Image = typing.Iterable[Line]

def syntax(lines:typing.Iterable[str], syntype:str, qualifier=None, adjustment=0) -> Image:
	"""
	# Generator producing sequences of line text for a syntax node.

	# [ Parameters ]
	# /lines/
		# Iterator of syntax lines without newlines.
	# /syntype/
		# The syntax type of &lines.
	# /qualifier/
		# The suffix of the syntax command line.
	# /adjustment/
		# Indentation level adjustment.
	"""
	si = "\t" * (1 + max(0, adjustment))

	yield [
		si[:-1], "#!" + syntype,
		("" if not qualfier else " " + qualifier),
	]

	for line in lines:
		yield [si, line]

def section_path(rdepth:int, rmultiple:typing.Optional[int], *path:str) -> Line:
	"""
	# Construct a section selector from a relative depth and a section identifier path.
	"""
	if rmultiple is not None:
		x = (">" * (rdepth or 1)) + str(rmultiple)
	else:
		if rdepth < 0 or rdepth > 8:
			x = ">" + str(rdepth)
		else:
			x = ">" * rdepth

	return ["[ ", x, (" " if x else ""), " >> ".join(path), " ]"]

def ambiguous_reference(string:str) -> Fragment:
	"""
	# Prefix the given string with an ampersand.
	"""
	return "&" + string

def section_reference(section_selector:str) -> Fragment:
	"""
	# Prefix the given string with an ampersand after enclosing it with brackets.
	"""
	return "&[" + section_selector + "]"

def hyperlink(url:str) -> Fragment:
	"""
	# Prefix the given string with an ampersand after enclosing it with angle brackets.
	"""
	return "&<" + url + ">"

def literal(string:str) -> Fragment:
	"""
	# Surround the string with grave-accents and replace any grave-accent within with two.
	"""
	return "`" + string.replace("`", "``") + "`"

_p_fragments = {
	('reference', 'ambiguous'): ambiguous_reference,
	('reference', 'hyperlink'): hyperlink,
	('reference', 'section'): section_reference,
	('literal', 'grave-accent'): literal,
	('text', 'normal'): (lambda x: x),
	('text', 'line-break'): (lambda x: " "),
	('text', 'emphasis'): (lambda x: x),
}

def paragraph(para:types.Paragraph) -> Image:
	"""
	# Generator producing an &Image representing the given &types.Paragraph.
	"""
	l = 0
	line = []

	for f in para:
		x = f[0].split('/', 2)
		x.append(None)

		pf = _p_fragments[(x[0], x[1])](f[1])

		if x[2] is not None:
			# Cast
			if x[0] != 'text':
				line.append("(" + x[2] + ")")
				l += len(line[-1])
			else:
				em = ('*' * int(x[2]))
				pf = em + pf + em

		line.append(pf)
		l += len(pf)

		if f[0] == 'text/line-break':
			yield line
			line = []
			l = 0

	if line:
		yield line

def inline_fragment(frag:types.Fragment) -> Fragment:
	return ''.join(paragraph((frag,)))

def _chapter(depth, node):
	for subnode in node[1]:
		typ, nodes, attr = subnode
		yield from _index[typ](depth, subnode)

def _section(depth, node):
	sd = node[2]
	p = section_path(sd['selector-level'] or 0, sd['selector-multiple'], *(sd['selector-path'] or ()))
	yield (depth, p)
	yield (depth, [""])
	yield from _tree(depth, node[1])

def _syn(depth, syntax):
	s = syntax[2]

	kl = ["#!", s['type']]
	if s.get('qualifier'):
		kl.append(" " + s['qualifier'])

	yield (depth, kl)
	sld = depth + 1
	for sl in syntax[1]:
		yield (sld, sl[1])

def _para(depth, node, Paragraph=types.Paragraph):
	if isinstance(node[1], Paragraph):
		pg = node[1]
	else:
		pg = document.export(node[1])

	for l in paragraph(pg):
		if l and l[-1] == ' ':
			l[-1] = ''
		yield (depth, l)
	yield (0, [""])

def _list(depth, node, list_type):
	for i in node[1]:
		assert i[0] == 'item'

		# First node must be a paragraph; empty is fine.
		i1 = i[1][0]
		assert i1[0] == 'paragraph'

		*init, last = _para(depth, i1)
		if not init:
			yield (depth, [list_type])
		else:
			init[0][1].insert(0, list_type)
			yield init[0]
			yield from (
				(x[0]+1, x[1]) for x in init[1:]
			)

		remainder = i[1][1:]
		if remainder:
			if init:
				yield (0, [""])
			yield from _tree(depth+1, i[1][1:])

	# Force line break to avoid paragraphs from being mistakenly joined.
	yield (depth, [""])

def _sequence(depth, node):
	return _list(depth, node, "# ")

def _set(depth, node):
	return _list(depth, node, "- ")

def _dictionary(depth, node, Paragraph=types.Paragraph):
	for item in node[1]:
		k, v = item[1]
		if isinstance(k[1], Paragraph):
			kp = k[1]
		else:
			kp = document.export(k[1])
		kl = ["/"]
		kl.extend(*paragraph(kp))
		kl.append("/")

		if len(v[1]) == 1 and v[1][0][0] == 'syntax':
			# ('syntax') only item.
			syntax = v[1][0]
			s = syntax[2]

			kl.append("#!" + s['type'])
			if s.get('qualifier'):
				kl.append(" " + s['qualifier'])

			yield (depth, kl)
			sld = depth + 1
			for sl in syntax[1]:
				yield (sld, sl[1])
		else:
			yield (depth, kl)
			yield from _tree(depth+1, v[1])

def _admonition(depth, node):
	ad = node[2]
	init = ["! ", ad['type'], ":"]
	if ad.get('title'):
		init.append(ad['title'])

	yield (depth, init)
	yield from _tree(depth+1, node[1])

_index = {
	'section': _section,
	'chapter': _chapter,
	'paragraph': _para,
	'syntax': _syn,
	'admonition': _admonition,

	'set': _set,
	'sequence': _sequence,
	'dictionary': _dictionary,

	# No-op element type often providing additional metadata.
	'void': (lambda x, y: ()),
}

def _tree(depth, nodes):
	for node in nodes:
		typ, nodes, attr = node
		yield from _index[typ](depth, node)

def tree(node, adjustment:int=0, indentation:str="\t", newline:str="\n") -> Image:
	"""
	# Produce the image representing the given node including newline characters.

	# [ Parameters ]
	# /node/
		# Any document node.
	# /adjustment/
		# The indentation difference to render Lines with. Zero by default.
	# /indentation/
		# The indentation character or sequence to render lines with.
	# /newline/
		# The character or sequence to append to each line in the image.
		# May be an empty string to supress line terminators.
	"""
	for il, lc in _tree(0, node[1]):
		lc.insert(0, (il+adjustment)*indentation)
		lc.append(newline)
		yield "".join(lc)

def elements(nodes, adjustment:int=0, indentation:str="\t", newline:str="\n") -> Image:
	"""
	# Produce the image representing the given &nodes sequence.

	# [ Parameters ]
	# /nodes/
		# Sequence of arbitrary text elements.
	# /adjustment/
		# The indentation difference to render Lines with. Zero by default.
	# /indentation/
		# The indentation character or sequence to render lines with.
	# /newline/
		# The character or sequence to append to each line in the image.
		# May be an empty string to supress line terminators.
	"""
	for il, lc in _tree(0, nodes):
		lc.insert(0, (il+adjustment)*indentation)
		lc.append(newline)
		yield "".join(lc)

def chapter(node, adjustment:int=0, indentation:str="\t", newline:str="\n") -> Image:
	"""
	# Produce the image representing the given chapter node including newline characters.

	# [ Parameters ]
	# /node/
		# Any document node.
	# /adjustment/
		# The indentation difference to render Lines with. Zero by default.
	# /indentation/
		# The indentation character or sequence to render lines with.
	# /newline/
		# The character or sequence to append to each line in the image.
		# May be an empty string to supress line terminators.
	"""
	for il, lc in _chapter(0, node):
		lc.insert(0, (il+adjustment)*indentation)
		lc.append(newline)
		yield "".join(lc)
