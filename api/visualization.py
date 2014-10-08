#from __future__ import unicode_literals
from phaidra.settings import GRAPH_DATABASE_REST_URL

from django.conf.urls import url

from tastypie.authorization import ReadOnlyAuthorization
from tastypie.utils import trailing_slash
from tastypie.http import HttpBadRequest
from tastypie.resources import Resource

from neo4jrestclient.client import GraphDatabase

from datetime import datetime
import dateutil.parser

from app.models import Grammar

import json
import operator
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "phaidra.settings")
#import time


class VisualizationResource(Resource):
                            
    class Meta:
        #queryset = Word.objects.all()
        resource_name = 'visualization'
        authorization = ReadOnlyAuthorization()

    def prepend_urls(self, *args, **kwargs):    
        
        return [
            url(r"^(?P<resource_name>%s)/%s%s$" % (self._meta.resource_name, 'encountered', trailing_slash()), self.wrap_view('encountered'), name="api_%s" % 'encountered'),
            url(r"^(?P<resource_name>%s)/%s%s$" % (self._meta.resource_name, 'statistics', trailing_slash()), self.wrap_view('statistics'), name="api_%s" % 'statistics'),
            url(r"^(?P<resource_name>%s)/%s%s$" % (self._meta.resource_name, 'least_accurate', trailing_slash()), self.wrap_view('least_accurate'), name="api_%s" % 'least_accurate'),
            url(r"^(?P<resource_name>%s)/%s%s$" % (self._meta.resource_name, 'least_recently', trailing_slash()), self.wrap_view('least_recently'), name="api_%s" % 'least_recently')
            ]
        
    """
    prepare knowledge map
    """
    def calculateKnowledgeMap(self, user):
        
        gdb = GraphDatabase(GRAPH_DATABASE_REST_URL)    
        submissions = gdb.query("""MATCH (n:`User`)-[:submits]->(s:`Submission`) WHERE HAS (n.username) AND n.username =  '""" + user + """' RETURN s""")    
                    
        #filename = os.path.join(os.path.dirname(__file__), '../static/json/smyth.json')
        #fileContent = {}
        #with open(filename, 'r') as json_data:
            #fileContent = json.load(json_data); json_data.close()                                  
                        
        vocab = {}
        smyth = {}        
        lemmas = {}
        lemmaFreq = 0
        # flatten the smyth and collect the vocab knowledge
        for sub in submissions.elements:            
            
            try:     
                for word in sub[0]['data']['encounteredWords']:
                        
                    try:
                        vocab[word] = vocab[word]+1
                    except KeyError as k:
                        vocab[word] = 1
                        # if vocab appears first time, get the lemmas frequency (two vocs can have same lemma, so save lemma as key)
                        try:
                            lemma = gdb.query("""MATCH (l:`Lemma`)-[:values]->(n:`Word`) WHERE n.CTS = '""" + word + """' RETURN l.value, l.frequency""")
                            if lemma.elements[0][0] is not None and lemma.elements[0][0] != "":
                                lemmas[lemma.elements[0][0]] = lemma.elements[0][1]
                        # in case of weird submission test data for encounteredWords
                        except IndexError as i:
                            continue
                    if sub[0]['data']['smyth'] not in smyth:
                        # get the morph info via a file lookup of submission's smyth key, save params to test it on the words of the work
                        #smyth[sub[0]['data']['smyth']] = grammar[sub[0]['data']['smyth']]
                        try:
                            params = {}
                            grammar = Grammar.objects.filter(ref=sub[0]['data']['smyth'])[0].query.split('&')
                            for pair in params:
                                params[pair.split('=')[0]] = pair.split('=')[1] 
                            smyth[sub[0]['data']['smyth']] = params
                        except IndexError as k:
                            continue                        
            except KeyError as k:
                continue
        
        # get the lemma/vocab overall count
        for freq in lemmas:
            lemmaFreq = lemmaFreq + int(lemmas[freq])

        return [vocab, smyth, lemmas, lemmaFreq]
    
    
    def check_fuzzy_filters(self, filter, request_attribute, word_attribute ):
        
        if filter == 'contains':
            if request_attribute not in word_attribute:
                return True
        elif filter == 'startswith':    
            if not word_attribute.startswith(request_attribute):
                return True
        elif filter == 'endswith':
            if not word_attribute.endswith(request_attribute):
                return True
        elif filter == 'isnot':    
            if word_attribute == request_attribute:
                return True
            
        return False


    """
    returns visualization data on word-rage-, book- and work-level.
    """
    def encountered(self, request, **kwargs):
        
        data = {}
        gdb = GraphDatabase(GRAPH_DATABASE_REST_URL)
        
        # get the user
        if request.GET.get('user'):
            user = request.GET.get('user')
        else:
            user= request.user.username
            
        try:
            userTable = gdb.query("""MATCH (n:`User`) WHERE n.username =  '""" + user + """' RETURN n""")
            userNode = gdb.nodes.get(userTable[0][0]['self'])
        except:
            return self.error_response(request, {'error': 'Login or hand over user.'}, response_class=HttpBadRequest)
        
        #fo = open("foo.txt", "wb")
        #millis = int(round(time.time() * 1000))
        #fo.write("%s start encountered method, get user: \n" % millis)    
        
        # /api/v1/visualization/encountered/?format=json&level=word&range=urn:cts:greekLit:tlg0003.tlg001.perseus-grc:1.90.4:11-19&user=john
        # return knowledge infos to all words in the range
        if request.GET.get('level') == "word":
            
            knownDict = {}
            data['words'] = []
        
            # calculate CTSs of the word range
            wordRangeArray = []
            cts = request.GET.get('range')
            # get the stem
            endIndex = len(cts)-len(cts.split(':')[len(cts.split(':'))-1])
            rangeStem = cts[0:endIndex]        
            # get the numbers of the range and save the CTSs
            numbersArray = cts.split(':')[len(cts.split(':'))-1].split('-')
            ####### make an error code wrong range format here
            for num in range(int(numbersArray[0]), int(numbersArray[1])+1):
                wordRangeArray.append(rangeStem + str(num))
            
            # check for which words which knowledge is there                    
            for wordRef in wordRangeArray:

                table = gdb.query("""MATCH (l:`Lemma`)-[:values]->(w:`Word`) WHERE HAS (w.CTS) AND HAS (w.head) AND w.CTS = '""" +wordRef+ """' RETURN w,l""")
                word = gdb.nodes.get(table[0][0]['self'])
                lemma = gdb.nodes.get(table[0][1]['self'])
                
                value = word.properties['value']
                times_seen = 0
                morph_known = False
                syn_known = False
                voc_known = False
                CTS = wordRef
                
                # check the ends of a word's relationships
                for rel in userNode.relationships.outgoing(["knows_vocab"])[:]:
                    if word == rel.end:
                        times_seen = rel.properties['times_seen']
                        voc_known = True
                    if lemma == rel.end:
                        voc_known = True
                
                for rel in userNode.relationships.outgoing(["knows_grammar"])[:]:        
                    if word == rel.end:
                        morph_known = True
                                                                
                data['words'].append({'value': value, 'timesSeen' : times_seen, 'morphKnown': morph_known, 'synKnown': syn_known, 'vocKnown': voc_known, 'CTS': CTS})
                    
            return self.create_response(request, data)
        
        
        # /api/v1/visualization/encountered/?format=json&level=book&range=urn:cts:greekLit:tlg0003.tlg001.perseus-grc&user=john
        # doesn the same as level=word; old approach soo much faster, because of use of boolean doctionaries
        elif request.GET.get('level') == "book":
            
            knownDict = {}
            data['words'] = []
            # preprocess knowledge of a user
            callFunction = self.calculateKnowledgeMap(request.GET.get('user'))
            vocKnowledge = callFunction[0]
            smythFlat = callFunction[1]
            lemmas = callFunction[2]
            
            # get the sentences of that document
            sentenceTable = gdb.query("""MATCH (n:`Document`)-[:sentences]->(s:`Sentence`) WHERE HAS (s.CTS) AND n.CTS = '""" +request.GET.get('range')+ """' RETURN s ORDER BY ID(s)""")
            
            for s in sentenceTable.elements:
                node = gdb.nodes.get(s[0]['self'])
                words = gdb.query("""MATCH (s:`Sentence`)-[:words]->(w:`Word`) WHERE s.CTS = '""" +node.properties['CTS']+ """' RETURN w ORDER BY ID(w)""")
                
                for w in words:
                    word = w[0]
                    knownDict[word['data']['CTS']] = False
                    
                    know_the_word = False
                    for smyth in smythFlat:
                        # scan the submission for vocab information
                        if word['data']['CTS'] in vocKnowledge or word['data']['lemma'] in lemmas:
                            # loop over params to get morph known infos
                            # extract this maybe (hand over smyth, its value and word)
                            badmatch = False
                            
                            for p in smythFlat[smyth].keys():
                                
                                try:
                                    word['data'][p]
                                    if smythFlat[smyth][p] != word['data'][p]:
                                        badmatch = True
                                        break
                                # check for fuzzy filtering attributes
                                except KeyError as k:
                                    if len(p.split('__')) > 1:
                                        try:
                                            badmatch = self.check_fuzzy_filters(p.split('__')[1], smythFlat[smyth][p], word['data'][p.split('__')[0]])
                                        except KeyError as k:
                                            badmatch = True
                                            break
                                    else:
                                        badmatch = True
                                        break
                                
                            if not badmatch:
                                knownDict[word['data']['CTS']] = True
                                
                            # vocab of word knwn?
                            know_the_word = True 
                                
                    # save data
                    try:
                        data['words'].append({'value': word['data']['value'], 'timesSeen' : vocKnowledge[word['data']['CTS']], 'morphKnown': knownDict[word['data']['CTS']], 'synKnown': False, 'vocKnown': know_the_word, 'CTS': word['data']['CTS']})
                    except KeyError as e:
                        data['words'].append({'value': word['data']['value'], 'timesSeen' : 0, 'morphKnown': knownDict[word['data']['CTS']], 'synKnown': False, 'vocKnown': know_the_word, 'CTS': word['data']['CTS']})

            return self.create_response(request, data)
        
            
        # if the viz of a document is requested calcualate the numbers on all submissions and then the percentage of viz data
        # /api/v1/visualization/encountered/?format=json&level=document&range=urn:cts:greekLit:tlg0003.tlg001.perseus-grc&user=john
        elif request.GET.get('level') == "document":
            
            data['sentences'] = []
                
            # preprocess knowledge of a user
            callFunction = self.calculateKnowledgeMap(request.GET.get('user'))
            vocKnowledge = callFunction[0]
            smythFlat = callFunction[1]
            lemmas = callFunction[2] # values + freqs
                
            # get the sentences of that document
            sentenceTable = gdb.query("""MATCH (n:`Document`)-[:sentences]->(s:`Sentence`) WHERE HAS (s.CTS) AND n.CTS = '""" +request.GET.get('range')+ """' RETURN s ORDER BY ID(s)""")
            
            for s in sentenceTable.elements:
                
                node = gdb.nodes.get(s[0]['self'])            
                words = node.relationships.outgoing(types=["words"])
                
                # helper arrays also for statistics, contain the cts as a key and a boolean as an entry
                all = {}    
                vocabKnown = {}
                morphKnown = {}
                syntaxKnown = {}
                
                for w in words:
                
                    word = w.end
                    all[word.properties['CTS']] = True
                    vocabKnown[word.properties['CTS']] = False
                    morphKnown[word.properties['CTS']] = False
                    syntaxKnown[word.properties['CTS']] = False
                    # scan the submission for vocab information
                    for smyth in smythFlat:
                        # was this word seen?
                        # also already know the other words connected to known words via a lemma
                        if word.properties['CTS'] in vocKnowledge or word.properties['lemma'] in lemmas:    
                            
                            # if word morph already known don't apply filter again
                            if morphKnown[word.properties['CTS']]:
                                # loop over params to get morph known infos
                                badmatch = False
                                for p in smythFlat[smyth].keys():
                                    try:
                                        word.properties[p]
                                        if smythFlat[smyth][p] != word.properties[p]:
                                            badmatch = True
                                            break
                                    # check for fuzzy filtering attributes
                                    except KeyError as k:
                                        if len(p.split('__')) > 1:
                                            try:
                                                badmatch = self.check_fuzzy_filters(p.split('__')[1], smythFlat[smyth][p], word.properties[p.split('__')[0]])
                                            except KeyError as k:
                                                badmatch = True
                                                break                                                                                    
                                        else:
                                            badmatch = True
                                            break
                                
                                if not badmatch:
                                    morphKnown[word.properties['CTS']] = True # all params are fine                                            
                            
                            # know this vocab
                            vocabKnown[word.properties['CTS']] = True
                
                # after reading words calcualte percentages of aspects for the sentence
                sentLeng = len(words)
                aspects = {'one': 0.0, 'two': 0.0, 'three': 0.0}
                for cts in all.keys():
                    if vocabKnown[cts] and morphKnown[cts] and syntaxKnown[cts]:
                        aspects['three'] = aspects['three'] +1
                    elif vocabKnown[cts] and morphKnown[cts] or vocabKnown[cts] and syntaxKnown[cts] or morphKnown[cts] and syntaxKnown[cts]:
                        aspects['two'] = aspects['two'] +1    
                    elif vocabKnown[cts] or morphKnown[cts] or syntaxKnown[cts]:    
                        aspects['one'] = aspects['one'] +1    
                
                # and save the infos to the json
                data['sentences'].append({'CTS': node.properties['CTS'], 'lenth': len(words), 'one': aspects['one']/len(words), 'two' : aspects['two']/len(words), 'three': aspects['three']/len(words)})
            
            return self.create_response(request, data)        
        
        return self.error_response(request, {'error': 'Level parameter required.'}, response_class=HttpBadRequest)
    
    
    """
    Returns overall statistically learned information for displaying in the panels
    """
    def statistics(self, request, **kwargs):
        
        data = {}
        gdb = GraphDatabase(GRAPH_DATABASE_REST_URL)
        
        # get the user
        if request.GET.get('user'):
            user = request.GET.get('user')
        else:
            user= request.user.username
            
        try:
            userTable = gdb.query("""MATCH (n:`User`) WHERE n.username =  '""" + user + """' RETURN n""")
            userNode = gdb.nodes.get(userTable[0][0]['self'])
        except:
            return self.error_response(request, {'error': 'Login or hand over user.'}, response_class=HttpBadRequest)
        
        # preprocess knowledge of a user; callFunction = self.calculateKnowledgeMap(request.GET.get('user')); vocKnowledge = callFunction[0]; smythFlat = callFunction[1]; lemmaFreqs = callFunction[2]
        knows_vocab = 0
        knows_grammar = 0
        knows_syntax = 0    
        # get the sentences of that document
        sentenceTable = gdb.query("""MATCH (n:`Document`)-[:sentences]->(s:`Sentence`)-[:words]->(w:`Word`) WHERE HAS (n.CTS) AND n.CTS = '""" +request.GET.get('range')+ """' RETURN count(w)""")
        all = sentenceTable[0][0]
        
        sentenceTable = gdb.query("""MATCH (u:`User`)-[:knows_vocab]->(l:`Lemma`) RETURN l""")
        
        for lemma in sentenceTable:
            knows_vocab = knows_vocab + lemma[0]['data']['frequency'] 
        
        knows_grammar = len(userNode.relationships.outgoing(["knows_grammar"])[:])
        
        # after reading everything return the statistics
        data['statistics'] = {'all': all, 'vocab': float(knows_vocab)/float(all), 'morphology': float(knows_grammar)/float(all), 'syntax': float(knows_syntax)/float(all)}
    
        return self.create_response(request, data)
    
    
    """
    Returns some figures for grammar and title the user has struggled with
    """
    def least_accurate(self, request, **kwargs):
        
        data = {}
        data['accuracy_ranking'] = []
        gdb = GraphDatabase(GRAPH_DATABASE_REST_URL)
        
        accuracy = {}

        # process accuracy of grammar of submissions of a user
        gdb = GraphDatabase(GRAPH_DATABASE_REST_URL)    
        submissions = gdb.query("""MATCH (n:`User`)-[:submits]->(s:`Submission`) WHERE HAS (n.username) AND n.username =  '""" + request.GET.get('user') + """' RETURN s""")            
                                    
        # get the accuray per smyth key
        for sub in submissions.elements:                               
            try:
                accuracy[sub[0]['data']['smyth']].append(sub[0]['data']['accuracy'])  
            except KeyError as k:
                accuracy[sub[0]['data']['smyth']] = []
                accuracy[sub[0]['data']['smyth']].append(sub[0]['data']['accuracy'])
        
        # calculate the averages and sort by it
        average = {}
        for smyth in accuracy.keys():
            average[smyth] = 0.0
            for value in accuracy[smyth]:
                average[smyth] = average[smyth] + value
            average[smyth] = average[smyth]/len(accuracy[smyth]) 
        
        sorted_dict = sorted(average.iteritems(), key=operator.itemgetter(1))
        #sorted_reverse = sorted.reverse()                         
                
        for entry in sorted_dict:
            data['accuracy_ranking'].append({'smyth': entry[0], 'average': average[entry[0]],
                                             'title': Grammar.objects.filter(ref=entry[0])[0].title,
                                             'query': Grammar.objects.filter(ref=entry[0])[0].query})
    
        #return the json
        return self.create_response(request, data)
    
    
    """
    Returns some figures for grammar and title the user has struggled with
    """
    def least_recently(self, request, **kwargs):
        
        data = {}
        data['time_ranking'] = []
        gdb = GraphDatabase(GRAPH_DATABASE_REST_URL)
        
        time = {}

        # process time of grammar of submissions of a user
        gdb = GraphDatabase(GRAPH_DATABASE_REST_URL)    
        submissions = gdb.query("""MATCH (n:`User`)-[:submits]->(s:`Submission`) WHERE HAS (n.username) AND n.username =  '""" + request.GET.get('user') + """' RETURN s""")            
        
        # get the current time
        unix = datetime(1970,1,1)
                                    
        # get the accuray per smyth key
        for sub in submissions.elements:
            
            if len(sub[0]['data']['smyth']) == 0:
                return self.error_response(request, {'error': 'Smyth keys are necessary for calculating averaged lesson progress.'}, response_class=HttpBadRequest)
            
            t = dateutil.parser.parse(sub[0]['data']['timestamp'])
            diff = (t-unix).total_seconds()                                                                            
            try:                    
                time[sub[0]['data']['smyth']].append(diff)  
            except KeyError as k:
                time[sub[0]['data']['smyth']] = []
                time[sub[0]['data']['smyth']].append(diff)
        
        # calculate the averages and sort by it
        average = {}
        for smyth in time.keys():
            average[smyth] = 0.0
            for value in time[smyth]:
                average[smyth] = average[smyth] + value
                
            av = average[smyth]/len(time[smyth])
            av = datetime.fromtimestamp(int(av)).strftime('%Y-%m-%d %H:%M:%S')
            av = av.replace(' ', 'T')
            average[smyth] = av
        
        sorted_dict = sorted(average.iteritems(), key=operator.itemgetter(1))
        #sorted_reverse = sorted_dict.reverse()
                
        for entry in sorted_dict:
            data['time_ranking'].append({'smyth': entry[0],
                                         'average': average[entry[0]],
                                         'title': Grammar.objects.filter(ref=entry[0])[0].title,
                                         'query': Grammar.objects.filter(ref=entry[0])[0].query})
    
        #return the json
        return self.create_response(request, data)
    