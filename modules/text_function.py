import re
import pyperclip

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
                    pyperclip.copy(questions)
    return questions

def genRecodes(txtC):
    recodes=""
    for line in txtC.splitlines():
        if re.search("A_",line):
            pref=re.search(".*_",line).group()
            spaces=re.sub("_"," ",line)
            num=""
            for word in spaces.split():
                num=word
            recodes+="RECODE "+pref+num+"(1="+num+").\n"
            pyperclip.copy(recodes)
    return recodes

def genLabels(txtVars,txtOpt):
    labels="* Encoding: UTF-8.\n"
    num=0
    options=txtOpt.splitlines()
    serie=False
    serienum=1
    fist=""
    prev=""
    pref=""
    optqueue=[]
    for line in txtVars.splitlines():
        if re.search("A_",line):
            if not serie:
                serie=True
                first=line
                pref=re.search(".*_",line).group()
                option=re.search(",.*}",options[num]).group()[2:-1]
                optqueue.append(option)
                prev=line
            else:
                if pref==re.search(".*_",line).group():
                    option=re.search(",.*}",options[num]).group()[2:-1]
                    optqueue.append(option)
                    prev=line
                else:
                    labels+="VALUE LABELS "+first+" to "+ prev
                    count=1
                    for opt in optqueue:
                        labels+="\n"+str(count)+" \""+opt+"\""
                        count+=1
                    labels+=".\n\n"
                    optqueue=[]
                    first=line
                    pref=re.search(".*_",line).group()
                    option=re.search(",.*}",options[num]).group()[2:-1]
                    optqueue.append(option)
                    prev=line
        num+=1
    if serie:
        labels+="VALUE LABELS "+first+" to "+ prev
        count=1
        for opt in optqueue:
            labels+="\n"+str(count)+" \""+opt+"\""
            count+=1
        labels+=".\n\n"
    pyperclip.copy(labels)
    return labels
