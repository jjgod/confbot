import re
import random

allwords = []
lines = []
wordlist = []
first = []
after = []
			
useless = ['I\'m','he\'s','it\'s','she\'s','can\'t',
			'all','another','any','anybody','anyone','anything',
			'both',
			'each','either','everbody','everyone','everything',
			'few',
			'he','her','hers','herself','him','himself','his',
			'I','it','its','itself',
			'many','me','mine','my','myself',
			'neither','nobody','none','no one','nothing',
			'one','others','our','ours','ourselves',
			'several','she','some','somebody','someone','something',
			'that','their','theirs','them','themselves','these','they','this','this',
			'us','we','what','which','who','whom','whose',
			'you','your','yours','yourself','yourselves',
			'a','the','and','can','of','off','to','too','in']


#Run though the lines file and build an array of words.
def parseLineFile(linefile):
	f = file('lines.txt', 'a+')
	for line in f:
		line = line.strip()
		if line:
			words = re.sub('[^A-Za-z_0-9 \']+','', line).split()
			allwords.append(words)
			lines.append(line)
	f.close()
	return allwords, lines
	
#Split the inputed string into a cleaned and splited array.
def parseLine(input):
	words = re.sub('Hawk:','',input.strip())
	words = re.sub('[^A-Za-z_0-9 \']+','', words)
	words = words.split()
	print words
	return words
	
def clean_useless(input):
	j = None
	for i in useless:
		i = re.sub('\'','\\\'',i)
		if j:
			j = j + '|' + i
		else:
			j = i
	j = '(?i)\\b(' + j.strip() + ')\\b'
	#print j
	output = re.sub(j,'',input)
	return output
	
#Build a list of all known words once.
def buildKnown(allwords):
	i = 0
	while i < len(allwords):
		for j in allwords[i]:
			if j not in wordlist:
				wordlist.append(j)
		i = i + 1
	#print wordlist
	return wordlist
		

def chatReply(input):
	#List of all words in the input that have been said before.
	leftwords = []
	#Left word gets the first line list and mid pairs that down.
	leftword = None
	midword = None
	#Separate line sequences
	leftlines = []
	midlines = []
	linenum = []
	
	#Remove all useless words like "The" and "I'm"
	input = clean_useless(input)
	words = parseLine(input)
	#print words
	#Build a list of known words
	knownwords = buildKnown(chatarray)
	for i in words:
		#Check if a word in the input sentence is known yet.
		if i in knownwords:
			#If it is append it to a list.
			leftwords.append(i)
	#Get a random word from the list of known words in the input sentence.
	if len(leftwords) > 1:
		leftword = leftwords[random.randrange(1,len(leftwords))]
		midword = leftwords[random.randrange(1,len(leftwords))]
		while midword == leftword and len(leftwords) > 2:
			midword = leftwords[random.randrange(1,len(leftwords))]
	elif leftwords:
		leftword = leftwords[0]
		
	if conf.hawkchat.debug == 1:
		print "Leftword: ",leftword
		print "Midword: ",midword	
	
	if not leftword: #If there are no known words pick a random sentence.
		reply = chatlines[random.randrange(len(chatlines))]
	else:
		i = 0
		while i < len(chatlines):
			if leftword in chatarray[i]:
				if chatlines[i]:
					linenum.append(i)
					leftlines.append(chatlines[i])
			i = i + 1
		i = 0
		while i < len(linenum):
			j = linenum[i]
			if midword in chatarray[j]:
				if chatlines[j]:
					midlines.append(chatlines[j])
			i = i + 1
		#print "leftlines: ", leftlines
		#print "Midlines: ", midlines
		if midlines:
			if len(midlines) > 1:
				midline = midlines[random.randrange(len(midlines))]
			elif midlines:
				#print leftlines
				midline = midlines[0]
			else:
				midline = chatlines[random.randrange(len(chatlines))]
			print "Midline: ",midline
			reply = midline
		else:
			if len(leftlines) > 1:
				leftline = leftlines[random.randrange(len(leftlines))]
			elif leftlines:
				#print leftlines
				leftline = leftlines[0]
			else:
				leftline = chatlines[random.randrange(len(chatlines))]
			print "Leftline: ",leftline
			reply = leftline#leftline + rightline
	if reply:
		return reply
	return 0
		
		
