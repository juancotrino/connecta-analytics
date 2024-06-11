from io import BytesIO
import re
import pyperclip
import pyreadstat
from unidecode import unidecode

from modules.segment_spss import get_temp_file

def questionFinder(txtC):
    questions=""
    for line in txtC.splitlines():
        if re.search("^\s*[A-Z][1-9].*\..*",line):
            qu=re.search("¿.*\?",line)
            numques=line.split()[0]
            if re.search("[^.]$",numques):
                numques+="."
            if qu:
                qutrim=qu.group()[:-1]
                if re.search("¿.*\?",qutrim):
                    questions+=numques+" "+re.search("¿.*\?",qutrim).group()+"\n"
                else:
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

def genIncludesList(txtVars,txtNums,txtC):
    nums=[]
    ffirst=True
    num2=0
    for num in txtNums.splitlines():
        if ffirst:
            ffirst=False
        else:
            if int(num)==1:
               nums.append(int(num2))
            num2=int(num)
    vars=txtVars.splitlines()
    base=[]
    textall=txtC.splitlines()
    count=0
    for n in nums:
        opt=""
        for i in range(n):
            opt+=textall[count]
            count+=1
        preg=opt.split()
        numpreg=""
        textopt=""
        for tx in preg:
            if numpreg=="":
                numpreg=tx
            else:
                textopt+=unidecode(tx)
        base.append([numpreg,textopt.lower()])
    result=""
    for ele in base:
        numpreg=ele[0]
        contain=False
        option=ele[1].strip().lower()
        for x in vars:
            if numpreg==x:
                contain=True
                break
        if contain:
            if option=="1si2no":
                result+="sino\n"
            else:
                for question in base:
                    if option==question[1]:
                        contain=False
                        for x in vars:
                            if question[0]==x:
                                contain=True
                                break
                        if contain:
                            result+=question[0]+"\n"
                            break
    pyperclip.copy(result)
    return result

def categoryFinder(txtC):
    result=""
    count=0
    lines=txtC.splitlines()
    c=0
    for line in lines:
        if re.search("^\s*[A-Z][1-9].*\..*",line):
            numques=line.split()[0]
            if re.search("[^.]$",numques):
                numques+="."
            if lines[count-1]!="":
                if re.search("¿.*\?",line):
                    result+=numques+" "+lines[count-1]+ "\n"+re.search("¿.*\?",line).group()+"\n\n"
                else:
                    result+=numques+" "+lines[count-1]+ "\n"+ re.search("\s.*",line).group()+"\n\n"
            else:
                if re.search("¿.*\?",line):
                    result+=numques+" "+ re.search("¿.*\?",line).group()+"\n\n"
                else:
                    result+=numques+" "
                    for word in line.split():
                        if c==0:
                            c=1
                            continue
                        if re.search("^[A-ZÁÉÍÓÚ].*[A-ZÁÉÍÓÚ.]$",word):
                            continue
                        else:
                            result+=word+" "
                    result+="\n\n"
        count+=1
    pyperclip.copy(result)
    return result

def genRecodes2(txtC):
    result=""
    flag=True
    vars=[]
    num=""
    for line in txtC.splitlines():
        if flag:
            if re.search("^[A-Z][1-90]",line):
                vars.append(line)
            else:
                flag=False
        else:
            if re.search("[^\s]",line):
                result=""
    return result

def genLabels2(txtC):
    result=""
    for line in txtC.splitlines():
        result+=line.split()[0]+" \""+re.search("\s.*",line).group()[1:]+"\""+"\n"
    return result

def processSav(spss_file:BytesIO):
    temp_file_name = get_temp_file(spss_file)
    data, study_metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )



def processSavMulti(spss_file: BytesIO):
    temp_file_name = get_temp_file(spss_file)
    data, study_metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )
    vals=study_metadata.variable_value_labels
    recodes="* Encoding: UTF-8.\n"
    for line,scale in vals.items():
        if re.search("^[FPS].*A.*[1-90]",line):
            pref=re.search(".*A[^1-90]*",line).group()
            num=re.search("A.*",line).group()[1:]
            if not re.search("^[1-90]",num):
                num=num[1:]
            recodes+="RECODE "+pref+num+"(1="+num+").\n"
    recodes+="EXECUTE."
    labels="* Encoding: UTF-8.\n"
    serie=False
    prev=""
    pref=""
    optqueue=[]
    for line, scale in vals.items():
        if re.search("^[FPS].*A.*[1-90]",line):
            if not serie:
                serie=True
                first=line
                pref=re.search(".*A",line).group()
                option=scale.get(1).strip()
                optqueue.append(option)
                prev=line
            else:
                if pref==re.search(".*A",line).group():
                    if len(scale)>=1:
                        option=scale.get(1).strip()
                        optqueue.append(option)
                        prev=line
                else:
                    labels+="VALUE LABELS "+first+" to "+ prev
                    num=re.search("A.*",first).group()[1:]
                    if not re.search("^[1-90]",num):
                        num=num[1:]
                    count=int(num)
                    for opt in optqueue:
                        labels+="\n"+str(count)+" \""+opt+"\""
                        count+=1
                    labels+=".\n\n"
                    optqueue=[]
                    first=line
                    pref=re.search(".*A",line).group()
                    option=scale.get(1).strip()
                    optqueue.append(option)
                    prev=line
    if serie:
        labels+="VALUE LABELS "+first+" to "+ prev
        num=re.search("A.*",first).group()[1:]
        if not re.search("^[1-90]",num):
            num=num[1:]
        count=int(num)
        for opt in optqueue:
            labels+="\n"+str(count)+" \""+opt+"\""
            count+=1
        labels+=".\n\n"

    varia=""
    return recodes,labels
