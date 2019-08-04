import bioc
import csv
import io
import operator
import os
import pandas
import re

from nltk import word_tokenize
from string import punctuation


# taken from https://github.com/yfpeng/bioc
def parse_to_string(filename):
    with open(filename, 'r') as fp:
        collection = bioc.load(fp)

    return collection

def get_document(collection, name):
    ret = None
    for document in collection.documents:
        if document.id == name:
            ret = document

    if ret is None:
        print("Document not found!")

    return(ret)

def remove_duplicates(zipped_raw):

    zipped = []

    for i in reversed(range(0, len(zipped_raw))):
        keep = True
        j = i - 1
        while j >= 0:
            if zipped_raw[i][0] >= zipped_raw[j][0] and zipped_raw[i][1] <= zipped_raw[j][1]:
                keep = False
                break
            j = j - 1

        if keep:
            zipped.append(zipped_raw[i])

    zipped.reverse()
    return(zipped)

def match_concept(tokens, words, curr_idx):

    rez = None
    iter_count = 0
    for i in reversed(range(0, curr_idx+1)):
        if iter_count > 0:
            break
        iter_count += 1
        found = True
        j = i
        for word in words:
            #print(word.upper(), tokens[j].upper(), sep = ' ' )
            if word.upper() != tokens[j].upper():
                found = False
                break
            j += 1
            if j >= len(tokens):
                break

        if found:
            rez = i
            break

    return rez



def write_recipes():

    collection = parse_to_string("FoodBase_curated.xml")

    for document in collection.documents:
        text = document.infons['full_text'].strip()
        fname = './recipes/'+document.id+'.txt'
        with open(fname, 'w') as fp:
            fp.write(text)
    

def comparison_count(onto = None, verbose = False):

    if onto is None:
        print("No ontology selected!")
        return(-1)
    if onto not in ['OF', 'FOODON', 'SNOMEDCT']:
        print("No such ontology supported!")
        return(-1)

    path = './csv/' + onto 
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]

    collection = parse_to_string("FoodBase_curated.xml")

    ctr = 0
    FP_count = 0
    match_count = 0
    partial_count = 0
    FN_count = 0
    FPs = []
    recipe_ids = []
    for f in files:

        if ctr > 100000:
            break

        # ------ Getting data ------ #
        recipe_id = f.split('_')[0]
        recipe_ids.append(recipe_id)
        #recipe_id = recipe_id[0:1] + 'r' + recipe_id[1:]
        full_f = path + '/' + f

        document = get_document(collection, recipe_id)
        text = document.infons['full_text'].strip()
        tokens = word_tokenize(text)

        
        t_loc = []
        t_len = []
        t_text = []
        for annotation in document.annotations:
            t_loc.append(annotation.locations[0].offset)
            t_len.append(annotation.locations[0].length)
            t_text.append(annotation.text)

        
        ground_truth = list(zip(t_loc, t_len, t_text))


        df = pandas.read_csv(full_f, sep = ',', index_col=0, header = 0) 
        zipped_raw = list(zip(df['from'], df['to'], df['text']))
        zipped_raw.sort(key = lambda t: t[1] - t[0], reverse=True)

        # ------ Removing duplicates ------ #
        zipped = remove_duplicates(zipped_raw)
        zipped.sort(key=lambda x: x[0])

        # ------ Converting from char to token ------ #

        
        zipped_converted = []
        char_count = 1
        concept_idx = 0
        for i in range(0, len(tokens)):
            
            if concept_idx >= len(zipped) or char_count >= len(text):
                break

            if zipped[concept_idx][0] <= char_count:
                #print(i, zipped[concept_idx][0], char_count, zipped[concept_idx][2], sep = ' | ')

                words = word_tokenize(zipped[concept_idx][2])
                where = match_concept(tokens, words, i)

                if where is None:
                    FP_count += 1
                    FPs.append(words) 
                    
                else:
                    zipped_converted.append((where+1, zipped[concept_idx][1]-zipped[concept_idx][0] + 1,zipped[concept_idx][2]))
                concept_idx += 1
            #print("Char is: " + text[char_count-1])    
            char_count += len(tokens[i])
            #print("Char is: " + text[char_count-1] + " at " + str(char_count-1))
            #print("----")
            if text[char_count-1] == ' ':
                char_count += 1

            
        if verbose:
            print(zipped_converted)
            print(ground_truth)

        # ------ Sanity check ------ #

        for p in ground_truth:
            
            i = p[0] - 1
            for toks in word_tokenize(p[2]):
                assert(toks == tokens[i])
                i = i + 1    
        
        # ------ Counting matches, partials and misses (match, part, miss) ------ #
        match = 0
        part = 0
        miss = 0
        fp_t = 0
        vis = [False] * len(ground_truth)
        ctr = 0 
        for z in zipped_converted:
            found = False
            for ctr in range(0, len(ground_truth)):
                g = ground_truth[ctr]

                if z[0] == g[0] and z[1] == g[1]:
                    match += 1
                    if vis[ctr] and verbose:
                        print("Already visited!")
                    vis[ctr] = True
                    found = True
                    break
                elif z[0] == g[0] and z[1] < g[1]:
                    part += 1
                    if verbose:
                        print(z[2], g[2], sep=' | ')
                        if vis[ctr]:
                            print("Already visited!")
                    vis[ctr] = True
                    found = True
                    break
                elif z[0] > g[0] and z[0] < (g[0] + len(word_tokenize(g[2]))):
                    part += 1 
                    if verbose:
                        print(z[2], g[2], sep=' | ')
                        if vis[ctr]:
                            print("Already visited!")
                    vis[ctr]= True
                    found = True
                    break

            if not found:
                #print("Not found: ", z[2])
                fp_t += 1
                
        miss = vis.count(False)

        match_count += match
        partial_count += part
        FN_count += miss
        FP_count += fp_t
        if verbose:
            print("Total truth: ", len(ground_truth))
            print("Match: ", match)
            print("partial: ", part)
            print("FN(miss): ", miss)
            print("FP: ", fp_t)

            print(f, recipe_id, sep=' ')
            print('\n')
        ctr = ctr + 1

    #print(FPs)
    not_ann = 0
    for document in collection.documents:

        if document.id in recipe_ids:
            continue
        #print(document.id)
        FN_count += len(document.annotations)
        not_ann += 1




    print(onto)
    print("\tMatch: ", match_count)
    print("\tpartial: ", partial_count)
    print("\tFN(miss): ", FN_count)
    print("\tFP: ", FP_count)
    print("Total recipes annotated by ontology: " + str(len(recipe_ids)))
    print("Total recipes missed by ontology: " + str(not_ann))
    print("\n")
    

def find_index(full_tokens, chunk_tokens, pos):
    ret = -1


    for p in range(pos - 2, pos):
        is_good = True

        i = p
        for toks in chunk_tokens:
            if not (toks == full_tokens[i]):
                is_good = False
                break
            i = i + 1

        if is_good:
            ret = p
            break

    if ret > -1:
        return ret

    for p in range(pos, len(full_tokens)):

        
        if abs(p - pos) > 10:
            break

        is_good = True

        i = p
        for toks in chunk_tokens:
            if not (toks == full_tokens[i]):
                is_good = False
                break
            i = i + 1

        if is_good:
            ret = p
            break

    return ret

def compare_spelling(word1, word2, threshold):

    n = min(len(word1), len(word2))

    ret = 0
    for i in range(0, n):
        if word1[i] is not word2[i]:
            break
        ret += 1


    return ret < threshold
        


if __name__ == '__main__':
    
    comparison_count("SNOMEDCT")
    comparison_count("OF")
    comparison_count("FOODON")


    print("Done.")

