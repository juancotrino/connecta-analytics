import re



def questionFinder(txtC):
    questions=""
    for line in txtC.splitlines():
        if re.search("^\s*[A-Z][1-9].*\..*",line):
            qu=re.search("¿.*\?",line)
            numques=line.split()[0]
            if re.search("[^.]$",numques):
                numques+="."
            if qu:
                questions+=numques+" "+qu.group()+"\n"
            else:
                qu2=re.search("¿.*",line)
                if qu2:
                    questions+=numques+" "+qu2.group()+"\n"
                else:
                    flag=True
                    questions+=numques+" "
                    for word in line.split():
                        if flag:
                            flag=False
                            continue
                        if re.search("^[A-ZÁÉÍÓÚ].*[A-ZÁÉÍÓÚ.]$",word):
                            continue
                        else:
                            questions+=word+" "
                    questions+="\n"
    return questions
