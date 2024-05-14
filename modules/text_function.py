import re



def questionFinder(txtC):
    questions=""
    for line in txtC.splitlines():
        if re.search("^[A-Z][1-9].*",line):
            qu=re.search("¿.*\?",line)
            numques=line.split()[0]
            print(numques)
            if re.match("\.$",numques):
                numques+="."
            if qu:
                questions+=numques+" "+qu.group()+"\n"
            else:
                qu2=re.search("¿.*",line)
                if qu2:
                    questions+=numques+" "+qu2.group()+"\n"
                else:
                    for word in line.split():
                        if re.search("^[A-ZÁÉÍÓÚ].*[A-ZÁÉÍÓÚ.]$",word):
                            continue
                        else:
                            questions+=word+" "
                    questions+="\n"
    return questions
