from io import BytesIO
import re
import pyperclip
import pyreadstat
from unidecode import unidecode
from difflib import SequenceMatcher

from app.modules.segment_spss import get_temp_file

def questionFinder(txtC):
    questions=""
    for line in txtC.splitlines():
        if re.search("^\s*[A-Z][1-90].*\..*",line):
            qu=re.search("¿.*\?",line)
            numques=line.split()[0]
            while re.search("[^0-9]$",numques):
                numques=numques[:-1]
            if re.search("[^.]$",numques):
                numques+="."
            if qu:
                qutrim=qu.group()[:-1]
                if re.search("¿.*\?",qutrim):
                    pregu=re.search("¿.*\?",qutrim).group().split()[0][1:]
                    pregu2=" ".join(re.search("¿.*\?",qutrim).group().split()[1:])
                    questions+=numques+" ¿"+pregu.capitalize()+" "+pregu2+"\n"
                else:
                    pregu=qu.group().split()[0][1:]
                    pregu2=" ".join(qu.group().split()[1:])
                    questions+=numques+" ¿"+pregu.capitalize()+" "+pregu2+"\n"
            else:
                qu2=re.search("¿.*",line)
                if qu2:
                    preg1nonefirst=re.search(".*[^A-Z .ÁÉÍÓÚ]",qu2.group()[1:]).group().split()[0]
                    preg1none=" ".join(re.search(".*[^A-Z .ÁÉÍÓÚ]",qu2.group()[1:]).group().split()[1:])
                    questions+=numques+" ¿"+preg1nonefirst.capitalize()+" "+preg1none+"?\n"
                else:
                    questions+=numques+" "
                    questionstr=" ".join(line.split()[1:])
                    if re.search("[^A-Z .ÁÉÍÓÚ].*[^A-Z \-.ÁÉÍÓÚ]",questionstr):
                        questions+=re.search("([A-Z][a-z]|[^A-Z .ÁÉÍÓÚ]).*[^A-Z \-.ÁÉÍÓÚ]",questionstr).group()
                    else:
                        questions+=questionstr
                    questions+="\n"
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
    return recodes

def genLabels(txtQues,txtLabels):
    labels=""

    questions=[quest for quest in txtQues.splitlines()]
    idquestions=[]
    for ques in txtQues.splitlines():
        idquestions.append(ques.split()[0][:-1])
    for lab in txtLabels.splitlines():
        if lab=="":
            labels+="\n"
            continue
        idques=lab.split()[0]
        quest=" ".join(lab.split()[1:])
        if re.search("^[DF].*[0-9].*-",idques):
            preg=idques.split("-")[0]
            if re.search("_",preg):
                preg=preg.split("_")[0]
            try:
                labels+=questions[idquestions.index(preg)]
            except:
                labels+=preg+". "+" ".join(questions[idquestions.index(preg.split(".")[0])].split()[1:])
        elif re.search("^[PS].*[0-9].*-",idques):
            preg2=idques.split("-")[0]
            if len(preg2.split("_"))>1:
                preg=preg2.split("_")[0]
                visit=preg2.split("_")[1]
                labels+=preg+". "+visit+" "+ " ".join(questions[idquestions.index(preg)].split()[1:])
        elif re.search("^[DFPS][0-9]",idques):
            if len(idques.split("_"))>1:
                preg=idques.split("_")[0]
                visit=idques.split("_")[1]
                if re.search(preg, quest):
                    labels+=preg+". "+visit+" "+ " ".join(questions[idquestions.index(preg)].split()[1:])
                else:
                    labels+=preg+". "+visit+ quest[1:]
            else:
                if re.search(idques, quest):
                    labels+=idques+". "+ " ".join(questions[idquestions.index(idques)].split()[1:])
                else:
                    labels+=idques+". "+ quest[2:]
        else:
             labels+=lab
        labels+="\n"
    return labels

def genIncludesList(txtVars,txtNums,txtC,txtDep,txtNums2):
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


    nums2=[]
    ffirst=True
    num2=0
    for num in txtNums2.splitlines():
        if ffirst:
            ffirst=False
        else:
            if int(num)==1:
               nums2.append(int(num2))
            num2=int(num)
    textall2=txtDep.splitlines()
    base2=[]
    count=0
    for n in nums2:
        opt=""
        for i in range(n):
            opt+=textall2[count]
            count+=1
        preg=opt.split()
        numpreg=""
        textopt=""
        for tx in preg:
            if numpreg=="":
                numpreg=tx
            else:
                textopt+=unidecode(tx)
        base2.append([numpreg,textopt.lower()])
    result=""
    for var in base:
        numpreg=var[0]
        contain=False
        option=var[1].strip().lower()
        for x in vars:
            if numpreg==x:
                contain=True
                break
        if contain:
            if option=="1si2no":
                result+="sino\n"
            else:
                for question in base2:
                    if similar(option,question[1])>=0.9:
                        result+=question[0]+"\n"
                        break
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

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()
    #print("........................\n")
    #print(study_metadata.value_labels)
    #for i in range(10):
    #    print(study_metadata.column_names[i])
    #print(study_metadata.column_names)
    #for i in range(10):
    #    if "labels"+str(i) in study_metadata.value_labels:
    #       st=str(study_metadata.value_labels.get("labels"+str(i)))
    #        print (study_metadata.value_labels.get("labels"+str(i)))
    #        print(re.search("\'.*\'",st[:-2]).group())
