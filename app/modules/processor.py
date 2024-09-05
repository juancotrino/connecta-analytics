from collections import Counter
from io import BytesIO
import re
import pandas as pd
import numpy as np
import math
from app.modules.segment_spss import get_temp_file
from app.modules.text_function import processSavMulti
import pyreadstat

def getPreProcessCode(spss_file: BytesIO,xlsx_file: BytesIO):
    file_xlsx = get_temp_file(xlsx_file)
    varsList=pd.read_excel(file_xlsx,usecols="A,B",skiprows=3,names=["vars","varsTypes"])
    colVarsList=pd.melt(pd.read_excel(file_xlsx,nrows=2),var_name="colVars",value_name="colVarsNames").drop(0)
    inverseVarsList=pd.read_excel(file_xlsx,usecols="A,E",skiprows=3,names=["vars","inverses"]).dropna()
    inverseVarsList=inverseVarsList[inverseVarsList["inverses"]=="I"].iloc[:,0]
    scaleVarsList=pd.read_excel(file_xlsx,usecols="A,D",skiprows=3,names=["vars","scale"]).dropna()

    preprocesscode=""
    preprocesscode+=processSavMulti(spss_file)[1]+processSavMulti(spss_file)[0]
    preprocesscode+=getGroupCreateMultisCode(spss_file)
    if not inverseVarsList.empty:
        preprocesscode+=getInverseCodeVars(inverseVarsList)
    if not scaleVarsList.empty:
        preprocesscode+=getScaleCodeVars(spss_file,scaleVarsList)
    preprocesscode+="\nCOMPUTE TOTAL=1.\nVARIABLE LABELS TOTAL 'TOTAL'.\nVALUE LABELS TOTAL 1 \"TOTAL\".\nEXECUTE.\n"
    preprocesscode+=getCloneCodeVars(spss_file,xlsx_file)
    preprocesscode+=getPreProcessAbiertas(spss_file,xlsx_file)
    return preprocesscode

def getPreProcessCode2(spss_file: BytesIO):
    preprocesscode=processSavMulti(spss_file)[1]+processSavMulti(spss_file)[0]
    return preprocesscode


def getProcessCode2(spss_file: BytesIO,xlsx_file: BytesIO,checkinclude=False,rutaarchivo=""):
    result=getProcessCode(spss_file,xlsx_file,checkinclude)
    file_xlsx = get_temp_file(xlsx_file)
    nombrehoja=pd.read_excel(file_xlsx,usecols="O",skiprows=3,names=["name"]).dropna().iloc[0,0]
    try:
        sufijo=pd.read_excel(file_xlsx,usecols="P",skiprows=3,names=["name"]).dropna().iloc[0,0]
        sufijo=" "+str(sufijo)
    except:
        sufijo=""
    result+="\nOUTPUT MODIFY\n  /SELECT ALL EXCEPT (TABLES)\n  /DELETEOBJECT DELETE = YES."
    result+=("\nOUTPUT EXPORT\n  /CONTENTS  EXPORT=VISIBLE  LAYERS=VISIBLE  MODELVIEWS=PRINTSETTING\n  /XLSX  DOCUMENTFILE='"
                        +rutaarchivo+"'\n     OPERATION=CREATESHEET  SHEET='"+nombrehoja+sufijo+"'\n     LOCATION=LASTCOLUMN  NOTESCAPTIONS=NO.\n"
                        +"OUTPUT CLOSE NAME=*.\nEXECUTE.\n")
    temp_file_name = get_temp_file(spss_file)
    data, study_metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )
    result+="\n*___TOTAL____________________________________________________________________________\n ____________________________________________________________________________________\n ______"+nombrehoja+sufijo+"______________________________________________________________________________.\n"
    varsList=pd.read_excel(file_xlsx,usecols="M",skiprows=3,names=["varsSegment"]).dropna()["varsSegment"].tolist()
    varsList_segment=pd.read_excel(file_xlsx,usecols="N",skiprows=3,names=["vars_Segment"]).dropna()["vars_Segment"].tolist()

    if not varsList_segment:
        for var in varsList:
            refdict=study_metadata.variable_value_labels[var]
            refs_unique=data[var].dropna().unique()
            refs_unique.sort()
            for refindex in refs_unique:
                name_var=re.sub("[()\-+áéíóú]","",refdict[refindex].replace(" ","_"))
                name_dataset=name_var
                name_sheet=nombrehoja+" "+refdict[refindex].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")+sufijo
                if len(name_sheet)>30:
                    name_sheet=nombrehoja+" "+refdict[refindex].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")[:10]+sufijo
                result+="DATASET ACTIVATE REF_"+name_dataset+".\n"
                condition=data[var]==refindex
                result+=getProcessCode(spss_file,xlsx_file,checkinclude,condition=condition)
                result+="\nOUTPUT MODIFY\n  /SELECT ALL EXCEPT (TABLES)\n  /DELETEOBJECT DELETE = YES."
                result+=("\nOUTPUT EXPORT\n  /CONTENTS  EXPORT=VISIBLE  LAYERS=VISIBLE  MODELVIEWS=PRINTSETTING\n  /XLSX  DOCUMENTFILE='"
                            +rutaarchivo+"'\n     OPERATION=CREATESHEET  SHEET='"+name_sheet+"'\n     LOCATION=LASTCOLUMN  NOTESCAPTIONS=NO.\n"
                            +"OUTPUT CLOSE NAME=*.\n")
                result+="DATASET CLOSE REF_"+name_dataset+".\n"
            result+="\n*____________________________________________________________________________________\n ______"+var+"______________________________________________________________________________\n ______"+nombrehoja+sufijo+"______________________________________________________________________________.\nEXECUTE.\n"
    else:
        for var_segment in varsList_segment:
                refdict_segment=study_metadata.variable_value_labels[var_segment]
                refs_segment_unique=data[var_segment].dropna().unique()
                refs_segment_unique.sort()
                for refindex_segment in refs_segment_unique:
                    name_var_segment=re.sub("[()\-+áéíóú]","",refdict_segment[refindex_segment].replace(" ","_"))
                    for var in varsList:
                        refdict=study_metadata.variable_value_labels[var]
                        refs_unique=data[var].dropna().unique()
                        refs_unique.sort()
                        for refindex in refs_unique:
                            name_var=re.sub("[()\-+áéíóú]","",refdict[refindex].replace(" ","_"))
                            name_dataset=name_var+"_"+name_var_segment
                            name_sheet=nombrehoja+" "+refdict[refindex].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")+" "+refdict_segment[refindex_segment].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")+sufijo
                            if len(name_sheet)>30:
                                name_sheet=nombrehoja+" "+refdict[refindex].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")[:10]+" "+refdict_segment[refindex_segment].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")[:10]+sufijo
                            result+="DATASET ACTIVATE REF_"+name_dataset+".\n"
                            condition1=data[var]==refindex
                            condition2=data[var_segment]==refindex_segment
                            condition=condition1&condition2
                            result+=getProcessCode(spss_file,xlsx_file,checkinclude,condition=condition)
                            result+="\nOUTPUT MODIFY\n  /SELECT ALL EXCEPT (TABLES)\n  /DELETEOBJECT DELETE = YES."
                            result+=("\nOUTPUT EXPORT\n  /CONTENTS  EXPORT=VISIBLE  LAYERS=VISIBLE  MODELVIEWS=PRINTSETTING\n  /XLSX  DOCUMENTFILE='"
                                        +rutaarchivo+"'\n     OPERATION=CREATESHEET  SHEET='"+name_sheet+"'\n     LOCATION=LASTCOLUMN  NOTESCAPTIONS=NO.\n"
                                        +"OUTPUT CLOSE NAME=*.\n")
                            result+="DATASET CLOSE REF_"+name_dataset+".\n"
                        result+=("\n*____________________________________________________________________________________"
                                 +"\n ______"+var+"______________________________________________________________________________"
                                 +"\n ______"+nombrehoja+sufijo+"_"+name_var_segment+"______________________________________________________________________________.\nEXECUTE.\n")


    result+="""*
                ⠸⣷⣦⠤⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣠⣤⠀⠀⠀
                ⠀⠙⣿⡄⠈⠑⢄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⠔⠊⠉⣿⡿⠁⠀⠀⠀
                ⠀⠀⠈⠣⡀⠀⠀⠑⢄⠀⠀⠀⠀⠀⠀⠀⠀⠀⡠⠊⠁⠀⠀⣰⠟⠀⠀⠀⠀⠀
                ⠀⠀⠀⠀⠈⠢⣄⠀⡈⠒⠊⠉⠁⠀⠈⠉⠑⠚⠀⠀⣀⠔⢊⣠⠤⠒⠊⡽⠀⠀
                ⠀⠀⠀⠀⠀⠀⠀⡽⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠩⡔⠊⠁⠀⠀⠀⠀⠀⠀⠇
                ⠀⠀⠀⠀⠀⠀⠀⡇⢠⡤⢄⠀⠀⠀⠀⠀⡠⢤⣄⠀⡇⠀⠀⠀⠀⠀⠀⠀⢰⠀
                ⠀⠀⠀⠀⠀⠀⢀⠇⠹⠿⠟⠀⠀⠤⠀⠀⠻⠿⠟⠀⣇⠀⠀⡀⠠⠄⠒⠊⠁⠀
                ⠀⠀⠀⠀⠀⠀⢸⣿⣿⡆⠀⠰⠤⠖⠦⠴⠀⢀⣶⣿⣿⠀⠙⢄⠀⠀⠀⠀⠀⠀
                ⠀⠀⠀⠀⠀⠀⠀⢻⣿⠃⠀⠀⠀⠀⠀⠀⠀⠈⠿⡿⠛⢄⠀⠀⠱⣄⠀⠀⠀⠀
                ⠀⠀⠀⠀⠀⠀⠀⢸⠈⠓⠦⠀⣀⣀⣀⠀⡠⠴⠊⠹⡞⣁⠤⠒⠉⠀⠀⠀⠀⠀
                ⠀⠀⠀⠀⠀⠀⣠⠃⠀⠀⠀⠀⡌⠉⠉⡤⠀⠀⠀⠀⢻⠿⠆⠀⠀⠀⠀⠀⠀⠀
                ⠀⠀⠀⠀⠀⠰⠁⡀⠀⠀⠀⠀⢸⠀⢰⠃⠀⠀⠀⢠⠀⢣⠀⠀⠀⠀⠀⠀⠀⠀
                ⠀⠀⠀⢶⣗⠧⡀⢳⠀⠀⠀⠀⢸⣀⣸⠀⠀⠀⢀⡜⠀⣸⢤⣶⠀⠀⠀⠀⠀⠀
                ⠀⠀⠀⠈⠻⣿⣦⣈⣧⡀⠀⠀⢸⣿⣿⠀⠀⢀⣼⡀⣨⣿⡿⠁⠀⠀⠀⠀⠀⠀
                ⠀⠀⠀⠀⠀⠈⠻⠿⠿⠓⠄⠤⠘⠉⠙⠤⢀⠾⠿⣿⠟⠋⠀⠀
                        ░░░░░░░░║░░░
                        ░░░╔╗╦╗╔╣░░░
                        ░░░╠╝║║║║░░░
                        ░░░╚╝╝╚╚╩░░░
                        ░░░░░░░░░░░░
                ."""
    return result

def getProcessCode(spss_file: BytesIO,xlsx_file: BytesIO,checkinclude=False,condition=None):

    file_xlsx = get_temp_file(xlsx_file)
    varsList=pd.read_excel(file_xlsx,usecols="A,B,D,E",skiprows=3,names=["vars","varsTypes","Scales","descendOrder"]).dropna(subset=["vars"])
    colVarsList=pd.melt(pd.read_excel(file_xlsx,nrows=2),var_name="colVars",value_name="colVarsNames").drop(0)
    result=""
    colvars=colVarsList.iloc[:,0]
    temp_file_name = get_temp_file(spss_file)
    data, study_metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )
    for i in range(len(colvars)):
        var=colvars[i+1]
        if re.search("^[PFSV].*[1-90].*A",var):
            colvars[i+1]="$COL_"+re.search(".*A",var).group()[:-1]
        else:
            colvars[i+1]="COL_"+var

    for i in range(len(varsList)):
        if varsList.iloc[i][1]!="A":
            if varsList.iloc[i][3]!="D":
                result+=writeQuestion(varsList.iloc[i][0],varsList.iloc[i][1],colvars,includeall=checkinclude)
            else:
                result+=writeQuestion(varsList.iloc[i][0],varsList.iloc[i][1],colvars,descendingorder=True,includeall=checkinclude)
            if not pd.isnull(varsList.iloc[i][2]) and not pd.isnull(varsList.iloc[i][3]) and not varsList.iloc[i][3] in ["I","D"]:
                varlabeloriginal=""
                for var, label in study_metadata.column_names_to_labels.items():
                    if var==varsList.iloc[i][0]:
                        varlabeloriginal=label
                for tipo in str(varsList.iloc[i][3]).split():
                    if tipo=="T2B":
                        result+="\nDELETE VARIABLES "+varsList.iloc[i][2]+tipo+".\nEXECUTE."
                        result+="\nSPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="+varsList.iloc[i][2]+"\n/OPTIONS FIX=\""+tipo+"\" FIXTYPE=SUFFIX ACTION=RUN.\nEXECUTE."
                        result+="\nVALUE LABELS "+varsList.iloc[i][2]+tipo+" 1 \""+tipo+"\"."
                        result+="\nRECODE "+varsList.iloc[i][2]+tipo+" (5=1) (4=1) (3=SYSMIS) (2=SYSMIS) (1=SYSMIS).\nEXECUTE.\n"
                        result+="\nVARIABLE LABELS "+varsList.iloc[i][0]+" \""+varlabeloriginal+" - "+tipo+"\".\nEXECUTE.\n"
                        result+=writeQuestion(varsList.iloc[i][0],varsList.iloc[i][1],colvars,includeall=checkinclude,varanidada=varsList.iloc[i][2]+tipo)
                    elif tipo=="MB":
                        result+="\nDELETE VARIABLES "+varsList.iloc[i][2]+tipo+".\nEXECUTE."
                        result+="\nSPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="+varsList.iloc[i][2]+"\n/OPTIONS FIX=\""+tipo+"\" FIXTYPE=SUFFIX ACTION=RUN.\nEXECUTE."
                        result+="\nVALUE LABELS "+varsList.iloc[i][2]+tipo+" 1 \""+tipo+"\"."
                        result+="\nRECODE "+varsList.iloc[i][2]+tipo+" (5=SYSMIS) (4=SYSMIS) (3=1) (2=SYSMIS) (1=SYSMIS).\nEXECUTE.\n"
                        result+="\nVARIABLE LABELS "+varsList.iloc[i][0]+" \""+varlabeloriginal+" - "+tipo+"\"."
                        result+=writeQuestion(varsList.iloc[i][0],varsList.iloc[i][1],colvars,includeall=checkinclude,varanidada=varsList.iloc[i][2]+tipo)
                    elif tipo=="B2B":
                        result+="\nDELETE VARIABLES "+varsList.iloc[i][2]+tipo+".\nEXECUTE."
                        result+="\nSPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="+varsList.iloc[i][2]+"\n/OPTIONS FIX=\""+tipo+"\" FIXTYPE=SUFFIX ACTION=RUN.\nEXECUTE."
                        result+="\nVALUE LABELS "+varsList.iloc[i][2]+tipo+" 1 \""+tipo+"\"."
                        result+="\nRECODE "+varsList.iloc[i][2]+tipo+" (5=SYSMIS) (4=SYSMIS) (3=SYSMIS) (2=1) (1=1).\nEXECUTE.\n"
                        result+="\nVARIABLE LABELS "+varsList.iloc[i][0]+" \""+varlabeloriginal+" - "+tipo+"\"."
                        result+=writeQuestion(varsList.iloc[i][0],varsList.iloc[i][1],colvars,includeall=checkinclude,varanidada=varsList.iloc[i][2]+tipo)
                    elif tipo=="B3B":
                        result+="\nDELETE VARIABLES "+varsList.iloc[i][2]+tipo+".\nEXECUTE."
                        result+="\nSPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="+varsList.iloc[i][2]+"\n/OPTIONS FIX=\""+tipo+"\" FIXTYPE=SUFFIX ACTION=RUN.\nEXECUTE."
                        result+="\nVALUE LABELS "+varsList.iloc[i][2]+tipo+" 1 \""+tipo+"\"."
                        result+="\nRECODE "+varsList.iloc[i][2]+tipo+" (5=SYSMIS) (4=SYSMIS) (3=1) (2=1) (1=1).\nEXECUTE.\n"
                        result+="\nVARIABLE LABELS "+varsList.iloc[i][0]+" \""+varlabeloriginal+" - "+tipo+"\"."
                        result+=writeQuestion(varsList.iloc[i][0],varsList.iloc[i][1],colvars,includeall=checkinclude,varanidada=varsList.iloc[i][2]+tipo)
                result+="\nVARIABLE LABELS "+varsList.iloc[i][0]+" \""+varlabeloriginal+"\"."
        elif varsList.iloc[i][1]=="A":
            result+=getProcessAbiertas(spss_file,xlsx_file,checkinclude,varsList.iloc[i][0],condition=condition)
    return result


def getPreProcessAbiertas(spss_file: BytesIO,xlsx_file: BytesIO):
    result=""
    temp_file_name = get_temp_file(spss_file)
    data, study_metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )
    file_xlsx = get_temp_file(xlsx_file)
    varsList=pd.read_excel(file_xlsx,usecols="A,C",skiprows=3,names=["vars","sheetNames"]).dropna()
    for i in range(len(varsList)):
        lcTable=pd.read_excel(file_xlsx,sheet_name=varsList.iloc[i][1],usecols="A,B",skiprows=1,names=["vars","sheetNames"])
        varAbierta=varsList.iloc[i][0]
        after=False
        prefix=re.search("^[PFSV].*[1-90].*A",varAbierta).group()
        multis=[]
        variab=""
        count=0
        labelvar=""
        for var, label in study_metadata.column_names_to_labels.items():
            if re.search("^[PFSV].*[1-90].*A",var):
                if re.search(".*A",var).group()==prefix:
                    multis.append(var)
                    if labelvar=="":
                        labelvar=label
        delmultis=[]
        for multi in multis:
            if study_metadata.column_names_to_labels[multi].startswith("otro"):
                delmultis.append(multi)
        for multi2 in delmultis:
            multis.remove(multi2)
        for i in range(len(multis)):
            variab+=multis[i]+" "
        result+= getAbiertasPreCode(variab,lcTable)
        if len(multis)>1:
            result+= writeAgrupMulti(prefix,multis,labelvar)
    return result

def getAbiertasPreCode(var,lcTable):
    abiertascode=""
    principal=""
    subcodes=[]
    options=[]
    for i in range(len(lcTable)):
        if str(lcTable.iloc[i][0]).strip()=="NETO":
            continue
        if lcTable.isnull().iloc[i][1]:
            subcodes.append(lcTable.iloc[i][0])
        else:
            if subcodes:
                abiertascode+="\nRECODE "+var
                for cod in subcodes:
                    abiertascode+=" ("+str(cod)+"="+str(principal)+")"
                abiertascode+="."
                subcodes=[]
            principal= lcTable.iloc[i][0]
            options.append((principal,lcTable.iloc[i][1]))
    abiertascode+="\nVALUE LABELS "+var
    for num,option in options:
        abiertascode+="\n"+str(num)+" \""+option+"\""
    abiertascode+=".\nEXECUTE.\n"
    return abiertascode

def getProcessAbiertas(spss_file: BytesIO,xlsx_file: BytesIO,checkinclude=False,namevar="",condition=None):
    result=""
    temp_file_name = get_temp_file(spss_file)
    data2, study_metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )

    if condition is None:
        data=data2
    else:
        data=data2[condition]

    file_xlsx = get_temp_file(xlsx_file)
    varsList=pd.read_excel(file_xlsx,usecols="A,C,D,E",skiprows=3,names=["vars","sheetNames","varanidada","typesegment"]).dropna(subset=["sheetNames"])
    colVarsList=pd.melt(pd.read_excel(file_xlsx,nrows=2),var_name="colVars",value_name="colVarsNames").drop(0)
    colvars=colVarsList.iloc[:,0]
    for i in range(len(colvars)):
        var=colvars[i+1]
        if re.search("^[PFSV].*[1-90].*A",var):
            colvars[i+1]="$COL_"+re.search(".*A",var).group()[:-1]
        else:
            colvars[i+1]="COL_"+var
    for i in range(len(varsList)):
        if namevar=="" or namevar==varsList.iloc[i][0]:
            lcTable=pd.read_excel(file_xlsx,sheet_name=varsList.iloc[i][1],usecols="A,B",skiprows=1,names=["vars","sheetNames"]).dropna()
            varAbierta=varsList.iloc[i][0]
            varlabeloriginal=""
            after=False
            prefix=re.search("^[PFSV].*[1-90].*A",varAbierta).group()
            multis=[]
            for var, label in study_metadata.column_names_to_labels.items():
                if var==varAbierta:
                    varlabeloriginal=label
                if re.search("^[PFSV].*[1-90].*A",var):
                    if re.search(".*A",var).group()==prefix:
                        multis.append(var)
            listNetos=[]
            parNeto=[]
            if lcTable.iloc[0][0]!="NETO":
                parNeto=["First",[]]
            for j in range(len(lcTable)):
                if lcTable.iloc[j][0]=="NETO":
                    if parNeto!=[]:
                        listNetos.append(parNeto)
                    parNeto=[lcTable.iloc[j][1],[]]
                elif lcTable.iloc[j][0]==95:
                    if parNeto!=[]:
                        listNetos.append(parNeto)
                    parNeto=["End",[95]]
                else:
                    parNeto[1].append(lcTable.iloc[j][0])
            if parNeto!=[]:
                listNetos.append(parNeto)
            listatotal=[]

            for var in multis:
                listatotal+=data[var].dropna().tolist()
            count=Counter(listatotal)
            listafinalorde=[]
            num=1
            for net in listNetos:
                if net[0]!="First" and net[0]!="End":
                    if any(count[ele]>0 for ele in net[1]):
                        listafinalorde.append(990+num)
                        result+="\nADD VALUE LABEL "
                        for multivar in multis:
                            result+=multivar+" "
                        result+=str(990+num) + " \"NETO "+net[0]+"\".\nEXECUTE.\n"
                        num+=1
                if net[0]!="End":
                    for in1 in count.most_common():
                        if in1[0] in net[1]:
                            listafinalorde.append(int(in1[0]))
                else:
                    for end in net[1]:
                        if count[end]>0:
                            listafinalorde.append(end)
            result+=writeAbiertasQuestion(varAbierta,colvars,listafinalorde,includeall=checkinclude)

            listatotaluniq=list(set(listatotal))
            for net in listNetos:
                if net[0]!="First" and net[0]!="End" and any(count[ele]>0 for ele in net[1]):
                    result+="\nDELETE VARIABLES "
                    for col in multis:
                        result+="NETO_"+col+" "
                    result+=".\nEXECUTE."
                    nombreneto=net[0].strip().replace(" ","_")+"_"+varAbierta
                    result+="\nSPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="
                    for col in multis:
                        result+=col+" "
                    result+="\n/OPTIONS FIX=\"NETO_\" FIXTYPE=PREFIX ACTION=RUN.\n"
                    newmultis=("NETO_"+variablee for variablee in multis)
                    result+="RECODE "
                    for newvar in newmultis:
                        result+=newvar+" "
                    result+="\n(SYSMIS=0)"
                    for num in listatotaluniq:
                        if num in net[1]:
                            result+=" ("+str(int(num))+"=1)"
                        else:
                            result+=" ("+str(int(num))+"=0)"
                    result+=".\nEXECUTE.\n\nCOMPUTE NETO_"+nombreneto+"="
                    newmultis=("NETO_"+variablee for variablee in multis)
                    for col in newmultis:
                        result+=col+"+"
                    result=result[:-1]+".\nRECODE NETO_"+nombreneto
                    for inde in range(len(multis)):
                        result+=" ("+str(inde+1)+"=1)"
                    result+=".\nEXECUTE.\nDELETE VARIABLES"
                    newmultis=("NETO_"+variablee for variablee in multis)
                    for newvar in newmultis:
                        result+=" "+newvar
                    result+=".\nEXECUTE.\n\nformats NETO_"+nombreneto+"(f8.0).\nVALUE LABELS NETO_"+nombreneto+" 1 \"NETO "+net[0].strip()+"\".\nEXECUTE.\n"
                    result+=writeQuestion("NETO_"+nombreneto,"T",colvars,includeall=checkinclude)


            if varsList.iloc[i][2] and varsList.iloc[i][3]:
                prefix=re.search("^[PFSV].*[1-90].*A",varAbierta).group()
                for tipo in str(varsList.iloc[i][3]).split():
                    if tipo=="T2B":
                        result+="\nDELETE VARIABLES "+varsList.iloc[i][2]+tipo+".\nEXECUTE."
                        result+="\nSPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="+varsList.iloc[i][2]+"\n/OPTIONS FIX=\""+tipo+"\" FIXTYPE=SUFFIX ACTION=RUN.\nEXECUTE."
                        result+="\nVALUE LABELS "+varsList.iloc[i][2]+tipo+" 1 \""+tipo+"\"."
                        result+="\nRECODE "+varsList.iloc[i][2]+tipo+" (5=1) (4=1) (3=SYSMIS) (2=SYSMIS) (1=SYSMIS).\nEXECUTE.\n"
                        result+= writeAgrupMulti(prefix,multis,varlabeloriginal+" - "+tipo)
                        condition1=data[varsList.iloc[i][2]]==5
                        condition2=data[varsList.iloc[i][2]]==4
                        filtro=condition1|condition2
                        result+=writeAbiertasQuestion(varAbierta,colvars,getListOrderConditions(multis,data,listNetos,filtro),includeall=checkinclude,varanidada=varsList.iloc[i][2]+tipo)
                        listatotal=[]
                        for var in multis:
                            listatotal+=data[filtro][var].tolist()
                        count2=Counter(listatotal)
                        listatotaluniq=list(set(listatotal))
                        for net in listNetos:
                            if net[0]!="First" and net[0]!="End" and any(count2[ele]>0 for ele in net[1]):
                                nombreneto=net[0].strip().replace(" ","_")+"_"+varAbierta
                                result+=writeQuestion("NETO_"+nombreneto,"T",colvars,includeall=checkinclude,varanidada=varsList.iloc[i][2]+tipo)
                    elif tipo=="MB":
                        result+="\nDELETE VARIABLES "+varsList.iloc[i][2]+tipo+".\nEXECUTE."
                        result+="\nSPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="+varsList.iloc[i][2]+"\n/OPTIONS FIX=\""+tipo+"\" FIXTYPE=SUFFIX ACTION=RUN.\nEXECUTE."
                        result+="\nVALUE LABELS "+varsList.iloc[i][2]+tipo+" 1 \""+tipo+"\"."
                        result+="\nRECODE "+varsList.iloc[i][2]+tipo+" (5=SYSMIS) (4=SYSMIS) (3=1) (2=SYSMIS) (1=SYSMIS).\nEXECUTE.\n"
                        result+= writeAgrupMulti(prefix,multis,varlabeloriginal+" - "+tipo)
                        filtro=data[varsList.iloc[i][2]]==3
                        result+=writeAbiertasQuestion(varAbierta,colvars,getListOrderConditions(multis,data,listNetos,filtro),includeall=checkinclude,varanidada=varsList.iloc[i][2]+tipo)
                        listatotal=[]
                        for var in multis:
                            listatotal+=data[filtro][var].tolist()
                        count2=Counter(listatotal)
                        listatotaluniq=list(set(listatotal))
                        for net in listNetos:
                            if net[0]!="First" and net[0]!="End" and any(count2[ele]>0 for ele in net[1]):
                                nombreneto=net[0].strip().replace(" ","_")+"_"+varAbierta
                                result+=writeQuestion("NETO_"+nombreneto,"T",colvars,includeall=checkinclude,varanidada=varsList.iloc[i][2]+tipo)
                    elif tipo=="B2B":
                        result+="\nDELETE VARIABLES "+varsList.iloc[i][2]+tipo+".\nEXECUTE."
                        result+="\nSPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="+varsList.iloc[i][2]+"\n/OPTIONS FIX=\""+tipo+"\" FIXTYPE=SUFFIX ACTION=RUN.\nEXECUTE."
                        result+="\nVALUE LABELS "+varsList.iloc[i][2]+tipo+" 1 \""+tipo+"\"."
                        result+="\nRECODE "+varsList.iloc[i][2]+tipo+" (5=SYSMIS) (4=SYSMIS) (3=SYSMIS) (2=1) (1=1).\nEXECUTE.\n"
                        result+= writeAgrupMulti(prefix,multis,varlabeloriginal+" - "+tipo)
                        condition1=data[varsList.iloc[i][2]]==1
                        condition2=data[varsList.iloc[i][2]]==2
                        filtro=condition1|condition2
                        result+=writeAbiertasQuestion(varAbierta,colvars,getListOrderConditions(multis,data,listNetos,filtro),includeall=checkinclude,varanidada=varsList.iloc[i][2]+tipo)
                        listatotal=[]
                        for var in multis:
                            listatotal+=data[filtro][var].tolist()
                        count2=Counter(listatotal)
                        listatotaluniq=list(set(listatotal))
                        for net in listNetos:
                            if net[0]!="First" and net[0]!="End" and any(count2[ele]>0 for ele in net[1]):
                                nombreneto=net[0].strip().replace(" ","_")+"_"+varAbierta
                                result+=writeQuestion("NETO_"+nombreneto,"T",colvars,includeall=checkinclude,varanidada=varsList.iloc[i][2]+tipo)
                    elif tipo=="B3B":
                        result+="\nDELETE VARIABLES "+varsList.iloc[i][2]+tipo+".\nEXECUTE."
                        result+="\nSPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="+varsList.iloc[i][2]+"\n/OPTIONS FIX=\""+tipo+"\" FIXTYPE=SUFFIX ACTION=RUN.\nEXECUTE."
                        result+="\nVALUE LABELS "+varsList.iloc[i][2]+tipo+" 1 \""+tipo+"\"."
                        result+="\nRECODE "+varsList.iloc[i][2]+tipo+" (5=SYSMIS) (4=SYSMIS) (3=1) (2=1) (1=1).\nEXECUTE.\n"
                        result+= writeAgrupMulti(prefix,multis,varlabeloriginal+" - "+tipo)
                        condition1=data[varsList.iloc[i][2]]==1
                        condition2=data[varsList.iloc[i][2]]==2
                        condition3=data[varsList.iloc[i][2]]==3
                        filtro=condition1|condition2|condition3
                        result+=writeAbiertasQuestion(varAbierta,colvars,getListOrderConditions(multis,data,listNetos,filtro),includeall=checkinclude,varanidada=varsList.iloc[i][2]+tipo)
                        listatotal=[]
                        for var in multis:
                            listatotal+=data[filtro][var].tolist()
                        count2=Counter(listatotal)
                        listatotaluniq=list(set(listatotal))
                        for net in listNetos:
                            if net[0]!="First" and net[0]!="End" and any(count2[ele]>0 for ele in net[1]):
                                nombreneto=net[0].strip().replace(" ","_")+"_"+varAbierta
                                result+=writeQuestion("NETO_"+nombreneto,"T",colvars,includeall=checkinclude,varanidada=varsList.iloc[i][2]+tipo)
            result+= writeAgrupMulti(prefix,multis,varlabeloriginal)
    return result

def getListOrderConditions(multis,data,listNetos,condition):
    listatotal=[]
    for var in multis:
        listatotal+=data[condition][var].tolist()
    count=Counter(listatotal)
    listafinalorde=[]
    num=1
    for net in listNetos:
        if net[0]!="First" and net[0]!="End":
            if any(count[ele]>0 for ele in net[1]):
                listafinalorde.append(990+num)
            num+=1
        if net[0]!="End":
            for i in count.most_common():
                if i[0] in net[1]:
                    listafinalorde.append(int(i[0]))
        else:
            for end in net[1]:
                if count[end]>0:
                    listafinalorde.append(end)
    return(listafinalorde)

def getPenaltysCode2(spss_file: BytesIO,xlsx_file: BytesIO,rutaarchivo=""):
    result=getPenaltysCode(xlsx_file)
    if getPenaltysCode(xlsx_file)!="":
        file_xlsx = get_temp_file(xlsx_file)
        nombrehoja="Penaltys"
        try:
            sufijo=pd.read_excel(file_xlsx,usecols="P",skiprows=3,names=["name"]).dropna().iloc[0,0]
            sufijo=" "+str(sufijo)
        except:
            sufijo=""
        result+=("\nOUTPUT EXPORT\n  /CONTENTS  EXPORT=VISIBLE  LAYERS=VISIBLE  MODELVIEWS=PRINTSETTING\n  /XLSX  DOCUMENTFILE='"
                         +rutaarchivo+"'\n     OPERATION=CREATESHEET  SHEET='"+nombrehoja+sufijo+"'\n     LOCATION=LASTCOLUMN  NOTESCAPTIONS=NO.\n"
                         +"OUTPUT CLOSE NAME=*.\nEXECUTE.\n")
        temp_file_name = get_temp_file(spss_file)
        data, study_metadata = pyreadstat.read_sav(
            temp_file_name,
            apply_value_formats=False
        )
        result+="\n*___TOTAL____________________________________________________________________________\n ____________________________________________________________________________________\n ______"+nombrehoja+sufijo+"______________________________________________________________________________.\n"
        varsList=pd.read_excel(file_xlsx,usecols="M",skiprows=3,names=["varsSegment"]).dropna()["varsSegment"].tolist()
        varsList_segment=pd.read_excel(file_xlsx,usecols="N",skiprows=3,names=["vars_Segment"]).dropna()["vars_Segment"].tolist()

        penaltys_code=getPenaltysCode(xlsx_file)
        if not varsList_segment:
            for var in varsList:
                refdict=study_metadata.variable_value_labels[var]
                refs_unique=data[var].dropna().unique()
                refs_unique.sort()
                for refindex in refs_unique:
                    name_var=re.sub("[()\-+áéíóú]","",refdict[refindex].replace(" ","_"))
                    name_dataset=name_var
                    name_sheet=nombrehoja+" "+refdict[refindex].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")+sufijo
                    if len(name_sheet)>30:
                        name_sheet=nombrehoja+" "+refdict[refindex].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")[:10]+sufijo
                    result+="DATASET ACTIVATE REF_"+name_dataset+".\n"
                    result+=penaltys_code
                    result+=("\nOUTPUT EXPORT\n  /CONTENTS  EXPORT=VISIBLE  LAYERS=VISIBLE  MODELVIEWS=PRINTSETTING\n  /XLSX  DOCUMENTFILE='"
                                +rutaarchivo+"'\n     OPERATION=CREATESHEET  SHEET='"+name_sheet+"'\n     LOCATION=LASTCOLUMN  NOTESCAPTIONS=NO.\n"
                                +"OUTPUT CLOSE NAME=*.\n")
                    result+="DATASET CLOSE REF_"+name_dataset+".\n"
                result+="\n*____________________________________________________________________________________\n ______"+var+"______________________________________________________________________________\n ______"+nombrehoja+sufijo+"______________________________________________________________________________.\nEXECUTE.\n"
        else:
            for var_segment in varsList_segment:
                    refdict_segment=study_metadata.variable_value_labels[var_segment]
                    refs_segment_unique=data[var_segment].dropna().unique()
                    refs_segment_unique.sort()
                    for refindex_segment in refs_segment_unique:
                        name_var_segment=re.sub("[()\-+áéíóú]","",refdict_segment[refindex_segment].replace(" ","_"))
                        for var in varsList:
                            refdict=study_metadata.variable_value_labels[var]
                            refs_unique=data[var].dropna().unique()
                            refs_unique.sort()
                            for refindex in refs_unique:
                                name_var=re.sub("[()\-+áéíóú]","",refdict[refindex].replace(" ","_"))
                                name_dataset=name_var+"_"+name_var_segment
                                name_sheet=nombrehoja+" "+refdict[refindex].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")+" "+refdict_segment[refindex_segment].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")+sufijo
                                if len(name_sheet)>30:
                                    name_sheet=nombrehoja+" "+refdict[refindex].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")[:10]+" "+refdict_segment[refindex_segment].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")[:10]+sufijo
                                result+="DATASET ACTIVATE REF_"+name_dataset+".\n"
                                result+=penaltys_code
                                result+=("\nOUTPUT EXPORT\n  /CONTENTS  EXPORT=VISIBLE  LAYERS=VISIBLE  MODELVIEWS=PRINTSETTING\n  /XLSX  DOCUMENTFILE='"
                                            +rutaarchivo+"'\n     OPERATION=CREATESHEET  SHEET='"+name_sheet+"'\n     LOCATION=LASTCOLUMN  NOTESCAPTIONS=NO.\n"
                                            +"OUTPUT CLOSE NAME=*.\n")
                                result+="DATASET CLOSE REF_"+name_dataset+".\n"
                            result+=("\n*____________________________________________________________________________________"
                                    +"\n ______"+var+"______________________________________________________________________________"
                                    +"\n ______"+nombrehoja+sufijo+"_"+name_var_segment+"______________________________________________________________________________.\nEXECUTE.\n")




        result+="""*
                    ⠸⣷⣦⠤⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣠⣤⠀⠀⠀
                    ⠀⠙⣿⡄⠈⠑⢄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⠔⠊⠉⣿⡿⠁⠀⠀⠀
                    ⠀⠀⠈⠣⡀⠀⠀⠑⢄⠀⠀⠀⠀⠀⠀⠀⠀⠀⡠⠊⠁⠀⠀⣰⠟⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠈⠢⣄⠀⡈⠒⠊⠉⠁⠀⠈⠉⠑⠚⠀⠀⣀⠔⢊⣠⠤⠒⠊⡽⠀⠀
                    ⠀⠀⠀⠀⠀⠀⠀⡽⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠩⡔⠊⠁⠀⠀⠀⠀⠀⠀⠇
                    ⠀⠀⠀⠀⠀⠀⠀⡇⢠⡤⢄⠀⠀⠀⠀⠀⡠⢤⣄⠀⡇⠀⠀⠀⠀⠀⠀⠀⢰⠀
                    ⠀⠀⠀⠀⠀⠀⢀⠇⠹⠿⠟⠀⠀⠤⠀⠀⠻⠿⠟⠀⣇⠀⠀⡀⠠⠄⠒⠊⠁⠀
                    ⠀⠀⠀⠀⠀⠀⢸⣿⣿⡆⠀⠰⠤⠖⠦⠴⠀⢀⣶⣿⣿⠀⠙⢄⠀⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠀⠀⢻⣿⠃⠀⠀⠀⠀⠀⠀⠀⠈⠿⡿⠛⢄⠀⠀⠱⣄⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠀⠀⢸⠈⠓⠦⠀⣀⣀⣀⠀⡠⠴⠊⠹⡞⣁⠤⠒⠉⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠀⣠⠃⠀⠀⠀⠀⡌⠉⠉⡤⠀⠀⠀⠀⢻⠿⠆⠀⠀⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠰⠁⡀⠀⠀⠀⠀⢸⠀⢰⠃⠀⠀⠀⢠⠀⢣⠀⠀⠀⠀⠀⠀⠀⠀
                    ⠀⠀⠀⢶⣗⠧⡀⢳⠀⠀⠀⠀⢸⣀⣸⠀⠀⠀⢀⡜⠀⣸⢤⣶⠀⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠈⠻⣿⣦⣈⣧⡀⠀⠀⢸⣿⣿⠀⠀⢀⣼⡀⣨⣿⡿⠁⠀⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠈⠻⠿⠿⠓⠄⠤⠘⠉⠙⠤⢀⠾⠿⣿⠟⠋⠀⠀
                          ░░░░░░░░║░░░
                          ░░░╔╗╦╗╔╣░░░
                          ░░░╠╝║║║║░░░
                          ░░░╚╝╝╚╚╩░░░
                          ░░░░░░░░░░░░
                    ."""
    return result

def getPenaltysCode(xlsx_file: BytesIO):
    try:
        file_xlsx = get_temp_file(xlsx_file)
        varsList=pd.read_excel(file_xlsx,usecols="A,B",skiprows=3,names=["vars","varsTypes"]).dropna()
        penaltyList=pd.read_excel(file_xlsx,usecols="K",skiprows=3,names=["penaltyVars"]).dropna()
        ref=penaltyList.iloc[0][0]
        penaltyList=penaltyList.drop(0)
        penaltyList=penaltyList.iloc[:,0]
        penaltyCode=""
        for i in range(len(varsList)):
            typevar=varsList.iloc[i][1]
            if typevar=="J":
                var1=varsList.iloc[i][0]
                var2=""
                try:
                    for penal in penaltyList:
                        if re.search("_.*",var1).group()==re.search("_.*",penal).group():
                            var2=penal
                            break
                except:
                    for penal in penaltyList:
                        var2=penal
                penaltyCode+=("\nCTABLES"
                    +"\n  /VLABELS VARIABLES="+var1+" "+ ref+" DISPLAY=LABEL  /VLABELS VARIABLES="+var2+ " DISPLAY=NONE"
                    +"\n  /PCOMPUTE &cat3 = EXPR([4] + [5])"
                    +"\n  /PPROPERTIES &cat3 LABEL = \"TOP TWO\" FORMAT=COUNT F40.0 HIDESOURCECATS=YES"
                    +"\n  /PCOMPUTE &cat2 = EXPR([3])"
                    +"\n  /PPROPERTIES &cat2 LABEL = \"JUST RIGHT\" FORMAT=COUNT F40.0 HIDESOURCECATS=YES"
                    +"\n  /PCOMPUTE &cat1 = EXPR([1] + [2])"
                    +"\n  /PPROPERTIES &cat1 LABEL = \"BOTTOM TWO\" FORMAT=COUNT F40.0 HIDESOURCECATS=YES"
                    +"\n  /TABLE "+var1+" [C][COUNT F40.0] + "+var1+" [C] > "+var2+" [C][COUNT F40.0] BY "+ref+" [C]"
                    +"\n  /SLABELS VISIBLE=NO"
                    +"\n  /CATEGORIES VARIABLES="+var1+" [1, 2, 3, 4, 5, &cat3, &cat2, &cat1, OTHERNM] EMPTY=INCLUDE TOTAL=YES POSITION=AFTER"
                    +"\n  /CATEGORIES VARIABLES="+var2+" ORDER=A KEY=VALUE EMPTY=INCLUDE TOTAL=YES POSITION=AFTER"
                    +"\n  /CATEGORIES VARIABLES="+ref+" ORDER=A KEY=VALUE EMPTY=EXCLUDE"
                    +"\n  /CRITERIA CILEVEL=95.")
        return penaltyCode
    except:
        return ""

def getCruces2(spss_file: BytesIO,xlsx_file: BytesIO,checkinclude=False,rutaarchivo=""):
    result=getCruces(spss_file,xlsx_file,checkinclude)
    if getCruces(spss_file,xlsx_file,checkinclude)!="":
        file_xlsx = get_temp_file(xlsx_file)
        nombrehoja="Cruces"
        try:
            sufijo=pd.read_excel(file_xlsx,usecols="P",skiprows=3,names=["name"]).dropna().iloc[0,0]
            sufijo=" "+str(sufijo)
        except:
            sufijo=""
        result+=("\nOUTPUT EXPORT\n  /CONTENTS  EXPORT=VISIBLE  LAYERS=VISIBLE  MODELVIEWS=PRINTSETTING\n  /XLSX  DOCUMENTFILE='"
                         +rutaarchivo+"'\n     OPERATION=CREATESHEET  SHEET='"+nombrehoja+sufijo+"'\n     LOCATION=LASTCOLUMN  NOTESCAPTIONS=NO.\n"
                         +"OUTPUT CLOSE NAME=*.\nEXECUTE.\n")
        temp_file_name = get_temp_file(spss_file)
        data, study_metadata = pyreadstat.read_sav(
            temp_file_name,
            apply_value_formats=False
        )
        result+="\n*___TOTAL____________________________________________________________________________\n ____________________________________________________________________________________\n ______"+nombrehoja+sufijo+"______________________________________________________________________________.\n"
        varsList=pd.read_excel(file_xlsx,usecols="M",skiprows=3,names=["varsSegment"]).dropna()["varsSegment"].tolist()
        varsList_segment=pd.read_excel(file_xlsx,usecols="N",skiprows=3,names=["vars_Segment"]).dropna()["vars_Segment"].tolist()

        if not varsList_segment:
            for var in varsList:
                refdict=study_metadata.variable_value_labels[var]
                refs_unique=data[var].dropna().unique()
                refs_unique.sort()
                for refindex in refs_unique:
                    name_var=re.sub("[()\-+áéíóú]","",refdict[refindex].replace(" ","_"))
                    name_dataset=name_var
                    name_sheet=nombrehoja+" "+refdict[refindex].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")+sufijo
                    if len(name_sheet)>30:
                        name_sheet=nombrehoja+" "+refdict[refindex].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")[:10]+sufijo
                    result+="DATASET ACTIVATE REF_"+name_dataset+".\n"
                    condition=data[var]==refindex
                    result+=getCruces(spss_file,xlsx_file,checkinclude,condition=condition)
                    result+="\nOUTPUT MODIFY\n  /SELECT ALL EXCEPT (TABLES)\n  /DELETEOBJECT DELETE = YES."
                    result+=("\nOUTPUT EXPORT\n  /CONTENTS  EXPORT=VISIBLE  LAYERS=VISIBLE  MODELVIEWS=PRINTSETTING\n  /XLSX  DOCUMENTFILE='"
                                +rutaarchivo+"'\n     OPERATION=CREATESHEET  SHEET='"+name_sheet+"'\n     LOCATION=LASTCOLUMN  NOTESCAPTIONS=NO.\n"
                                +"OUTPUT CLOSE NAME=*.\n")
                    result+="DATASET CLOSE REF_"+name_dataset+".\n"
                result+="\n*____________________________________________________________________________________\n ______"+var+"______________________________________________________________________________\n ______"+nombrehoja+sufijo+"______________________________________________________________________________.\nEXECUTE.\n"
        else:
            for var_segment in varsList_segment:
                    refdict_segment=study_metadata.variable_value_labels[var_segment]
                    refs_segment_unique=data[var_segment].dropna().unique()
                    refs_segment_unique.sort()
                    for refindex_segment in refs_segment_unique:
                        name_var_segment=re.sub("[()\-+áéíóú]","",refdict_segment[refindex_segment].replace(" ","_"))
                        for var in varsList:
                            refdict=study_metadata.variable_value_labels[var]
                            refs_unique=data[var].dropna().unique()
                            refs_unique.sort()
                            for refindex in refs_unique:
                                name_var=re.sub("[()\-+áéíóú]","",refdict[refindex].replace(" ","_"))
                                name_dataset=name_var+"_"+name_var_segment
                                name_sheet=nombrehoja+" "+refdict[refindex].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")+" "+refdict_segment[refindex_segment].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")+sufijo
                                if len(name_sheet)>30:
                                    name_sheet=nombrehoja+" "+refdict[refindex].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")[:10]+" "+refdict_segment[refindex_segment].replace("ñ","n").replace(".","").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ó","o")[:10]+sufijo
                                result+="DATASET ACTIVATE REF_"+name_dataset+".\n"
                                condition1=data[var]==refindex
                                condition2=data[var_segment]==refindex_segment
                                condition=condition1&condition2
                                result+=getCruces(spss_file,xlsx_file,checkinclude,condition=condition)
                                result+="\nOUTPUT MODIFY\n  /SELECT ALL EXCEPT (TABLES)\n  /DELETEOBJECT DELETE = YES."
                                result+=("\nOUTPUT EXPORT\n  /CONTENTS  EXPORT=VISIBLE  LAYERS=VISIBLE  MODELVIEWS=PRINTSETTING\n  /XLSX  DOCUMENTFILE='"
                                            +rutaarchivo+"'\n     OPERATION=CREATESHEET  SHEET='"+name_sheet+"'\n     LOCATION=LASTCOLUMN  NOTESCAPTIONS=NO.\n"
                                            +"OUTPUT CLOSE NAME=*.\n")
                                result+="DATASET CLOSE REF_"+name_dataset+".\n"
                            result+=("\n*____________________________________________________________________________________"
                                    +"\n ______"+var+"______________________________________________________________________________"
                                    +"\n ______"+nombrehoja+sufijo+"_"+name_var_segment+"______________________________________________________________________________.\nEXECUTE.\n")



        result+="""*
                    ⠸⣷⣦⠤⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣠⣤⠀⠀⠀
                    ⠀⠙⣿⡄⠈⠑⢄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⠔⠊⠉⣿⡿⠁⠀⠀⠀
                    ⠀⠀⠈⠣⡀⠀⠀⠑⢄⠀⠀⠀⠀⠀⠀⠀⠀⠀⡠⠊⠁⠀⠀⣰⠟⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠈⠢⣄⠀⡈⠒⠊⠉⠁⠀⠈⠉⠑⠚⠀⠀⣀⠔⢊⣠⠤⠒⠊⡽⠀⠀
                    ⠀⠀⠀⠀⠀⠀⠀⡽⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠩⡔⠊⠁⠀⠀⠀⠀⠀⠀⠇
                    ⠀⠀⠀⠀⠀⠀⠀⡇⢠⡤⢄⠀⠀⠀⠀⠀⡠⢤⣄⠀⡇⠀⠀⠀⠀⠀⠀⠀⢰⠀
                    ⠀⠀⠀⠀⠀⠀⢀⠇⠹⠿⠟⠀⠀⠤⠀⠀⠻⠿⠟⠀⣇⠀⠀⡀⠠⠄⠒⠊⠁⠀
                    ⠀⠀⠀⠀⠀⠀⢸⣿⣿⡆⠀⠰⠤⠖⠦⠴⠀⢀⣶⣿⣿⠀⠙⢄⠀⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠀⠀⢻⣿⠃⠀⠀⠀⠀⠀⠀⠀⠈⠿⡿⠛⢄⠀⠀⠱⣄⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠀⠀⢸⠈⠓⠦⠀⣀⣀⣀⠀⡠⠴⠊⠹⡞⣁⠤⠒⠉⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠀⣠⠃⠀⠀⠀⠀⡌⠉⠉⡤⠀⠀⠀⠀⢻⠿⠆⠀⠀⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠰⠁⡀⠀⠀⠀⠀⢸⠀⢰⠃⠀⠀⠀⢠⠀⢣⠀⠀⠀⠀⠀⠀⠀⠀
                    ⠀⠀⠀⢶⣗⠧⡀⢳⠀⠀⠀⠀⢸⣀⣸⠀⠀⠀⢀⡜⠀⣸⢤⣶⠀⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠈⠻⣿⣦⣈⣧⡀⠀⠀⢸⣿⣿⠀⠀⢀⣼⡀⣨⣿⡿⠁⠀⠀⠀⠀⠀⠀
                    ⠀⠀⠀⠀⠀⠈⠻⠿⠿⠓⠄⠤⠘⠉⠙⠤⢀⠾⠿⣿⠟⠋⠀⠀
                          ░░░░░░░░║░░░
                          ░░░╔╗╦╗╔╣░░░
                          ░░░╠╝║║║║░░░
                          ░░░╚╝╝╚╚╩░░░
                          ░░░░░░░░░░░░
                    ."""
    return result

def getCruces(spss_file: BytesIO,xlsx_file: BytesIO,checkinclude=False,condition=None):
    try:
        file_xlsx = get_temp_file(xlsx_file)
        varsList=pd.read_excel(file_xlsx,usecols="G,H,I,J",skiprows=3,names=["vars","varsTypes","crossVars","sheetname"]).dropna(subset=["vars"])
        crosscode=""
        for i in range(len(varsList)):
            for crossvar in varsList.iloc[i][2].split():
                if re.search("^[PFSV].*[1-90].*A",crossvar):
                    crossvar="$"+re.search(".*A",crossvar).group()[:-1]
                if varsList.iloc[i][1]!="A":
                    crosscode+=writeQuestion(varsList.iloc[i][0],varsList.iloc[i][1],[crossvar],includeall=checkinclude)
                else:
                    lcTable=pd.read_excel(file_xlsx,sheet_name=varsList.iloc[i][3],usecols="A,B",skiprows=1,names=["vars","sheetNames"]).dropna()
                    temp_file_name = get_temp_file(spss_file)
                    data2, study_metadata = pyreadstat.read_sav(
                        temp_file_name,
                        apply_value_formats=False
                    )
                    colvars=[crossvar]
                    if condition is None:
                        data=data2
                    else:
                        data=data2[condition]
                    varAbierta=varsList.iloc[i][0]
                    prefix=re.search("^[PFSV].*[1-90].*A",varAbierta).group()
                    multis=[]
                    for var, label in study_metadata.column_names_to_labels.items():
                        if re.search("^[PFSV].*[1-90].*A",var):
                            if re.search(".*A",var).group()==prefix:
                                multis.append(var)
                    listNetos=[]
                    parNeto=[]
                    if lcTable.iloc[0][0]!="NETO":
                        parNeto=["First",[]]
                    for j in range(len(lcTable)):
                        if lcTable.iloc[j][0]=="NETO":
                            if parNeto!=[]:
                                listNetos.append(parNeto)
                            parNeto=[lcTable.iloc[j][1],[]]
                        elif lcTable.iloc[j][0]==95:
                            if parNeto!=[]:
                                listNetos.append(parNeto)
                            parNeto=["End",[95]]
                        else:
                            parNeto[1].append(lcTable.iloc[j][0])
                    if parNeto!=[]:
                        listNetos.append(parNeto)
                    listatotal=[]

                    for var in multis:
                        listatotal+=data[var].dropna().tolist()
                    count=Counter(listatotal)
                    listafinalorde=[]
                    num=1
                    for net in listNetos:
                        if net[0]!="First" and net[0]!="End":
                            if any(count[ele]>0 for ele in net[1]):
                                listafinalorde.append(990+num)
                                crosscode+="\nADD VALUE LABEL "
                                for multivar in multis:
                                    crosscode+=multivar+" "
                                crosscode+=str(990+num) + " \"NETO "+net[0]+"\".\nEXECUTE.\n"
                                num+=1
                        if net[0]!="End":
                            for in1 in count.most_common():
                                if in1[0] in net[1]:
                                    listafinalorde.append(int(in1[0]))
                        else:
                            for end in net[1]:
                                if count[end]>0:
                                    listafinalorde.append(end)
                    crosscode+=writeAbiertasQuestion(varAbierta,colvars,listafinalorde,includeall=checkinclude)

                    listatotaluniq=list(set(listatotal))
                    for net in listNetos:
                        if net[0]!="First" and net[0]!="End" and any(count[ele]>0 for ele in net[1]):
                            crosscode+="\nDELETE VARIABLES "
                            for col in multis:
                                crosscode+="NETO_"+col+" "
                            crosscode+=".\nEXECUTE."
                            nombreneto=net[0].strip().replace(" ","_")+"_"+varAbierta
                            crosscode+="\nSPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="
                            for col in multis:
                                crosscode+=col+" "
                            crosscode+="\n/OPTIONS FIX=\"NETO_\" FIXTYPE=PREFIX ACTION=RUN.\n"
                            newmultis=("NETO_"+variablee for variablee in multis)
                            crosscode+="RECODE "
                            for newvar in newmultis:
                                crosscode+=newvar+" "
                            crosscode+="\n(SYSMIS=0)"
                            for num in listatotaluniq:
                                if num in net[1]:
                                    crosscode+=" ("+str(int(num))+"=1)"
                                else:
                                    crosscode+=" ("+str(int(num))+"=0)"
                            crosscode+=".\nEXECUTE.\n\nCOMPUTE NETO_"+nombreneto+"="
                            newmultis=("NETO_"+variablee for variablee in multis)
                            for col in newmultis:
                                crosscode+=col+"+"
                            crosscode=crosscode[:-1]+".\nRECODE NETO_"+nombreneto
                            for inde in range(len(multis)):
                                crosscode+=" ("+str(inde+1)+"=1)"
                            crosscode+=".\nEXECUTE.\nDELETE VARIABLES"
                            newmultis=("NETO_"+variablee for variablee in multis)
                            for newvar in newmultis:
                                crosscode+=" "+newvar
                            crosscode+=".\nEXECUTE.\n\nformats NETO_"+nombreneto+"(f8.0).\nVALUE LABELS NETO_"+nombreneto+" 1 \"NETO "+net[0].strip()+"\".\nEXECUTE.\n"
                            crosscode+=writeQuestion("NETO_"+nombreneto,"T",colvars,includeall=checkinclude)
        return crosscode
    except:
        return ""

def getVarsSav(spss_file: BytesIO):
    temp_file_name = get_temp_file(spss_file)
    data, study_metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )
    return study_metadata.column_names

def processSav(spss_file: BytesIO):
    temp_file_name = get_temp_file(spss_file)
    data, study_metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )

    variables_data = study_metadata.variable_value_labels
    p23labels=[labels for var,labels in variables_data.items() if var=='P23']
    print(p23labels)
    print(data)
    print(data.loc[:,'P23'].mean())
    print(p23labels[0].values())
    preg="P24"
    print(pd.crosstab(data.P23,data.RANGOS,rownames=["p23labels[0].values()"],normalize=True))
    de=pd.crosstab(data[preg],data.RANGOS,rownames=["val"],normalize=True,dropna=False)
    print(de*200)
    de2=de*200
    print(de2.round())
    print(data.loc[data['RANGOS']==2].loc[:,preg].mean())
    print(data.loc[data['RANGOS']==3].loc[:,preg].mean())
    print(data['RANGOS'].unique())
    print(pd.crosstab(data[preg],data.RANGOS,rownames=["val"],normalize='index',dropna=False))
    print(study_metadata.column_names)

def getCodePreProcess(spss_file: BytesIO,inversevars="",columnVars="",namedatasetspss="ConjuntoDatos1"):
    agrupresult=""
    temp_file_name = get_temp_file(spss_file)
    data, study_metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )
    serie=False
    prefix=""
    multis=[]
    label2=""
    for var, label in study_metadata.column_names_to_labels.items():
        if re.search("^[PFSV].*[1-90].*A",var):
            if not serie:
                multis=[]
                prefix=re.search(".*A",var).group()
                multis.append(var)
                serie=True
            else:
                if re.search(".*A",var).group()==prefix:
                    multis.append(var)
                else:
                    agrupresult+=writeAgrupMulti(prefix,multis,label2)
                    multis=[]
                    prefix=re.search(".*A",var).group()
                    multis.append(var)
        elif serie:
            agrupresult+=writeAgrupMulti(prefix,multis,label2)
            multis=[]
            serie=False
        label2=label

    inverserecodes=""
    for var in inversevars:
        inverserecodes+="\nRECODE "+var+" (5=1) (4=2) (2=4) (1=5)."
    inverserecodes+="\nEXECUTE."

    columnsclone="SPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="
    for col in columnVars:
        if not re.search("^[PFSV].*[1-90].*A",col):
            columnsclone+=col+" "
    columnsclone+="\n/OPTIONS FIX=\"COL_\" FIXTYPE=PREFIX ACTION=RUN.\n"

    for col in columnVars:
        if re.search("^[PFSV].*[1-90].*A",col):
            prefix=re.search(".*A",col).group()
            serie=False
            multis=[]
            label2=""
            for var, label in study_metadata.column_names_to_labels.items():
                if re.search(".A",var):
                    if re.search(".*A",var).group()==prefix:
                        serie=True
                        multis.append(var)
                        label2=label
                if serie:
                    if not re.search(".A",var) or re.search(".*A",var).group()!=prefix:
                        columnsclone+=writeAgrupMulti("COL_"+prefix,multis,label2)
                        break
    refdict=study_metadata.variable_value_labels["REF.1"]

    filterdatabase=""
    if namedatasetspss=="":
        namedatasetspss="ConjuntoDatos1"
    for refindex in data["REF.1"].unique():
        filterdatabase+="DATASET ACTIVATE "+ namedatasetspss+".\n"
        filterdatabase+="DATASET COPY REF_"+refdict[refindex]+".\nDATASET ACTIVATE REF_"+refdict[refindex]+".\nFILTER OFF.\nUSE ALL.\n"
        filterdatabase+="SELECT IF (REF.1 = "+str(int(refindex))+").\nEXECUTE.\n\n"
    return agrupresult,inverserecodes,columnsclone,filterdatabase

def getCodeProcess(spss_file: BytesIO,colvars,varsTxt,qtypesTxt,checkinclude=False):
    result=""
    varsProcess=[var for var in varsTxt.splitlines()]
    qtypes=[qtype for qtype in qtypesTxt.splitlines()]

    for i in range(len(colvars)):
        var=colvars[i]
        if re.search("^[PFSV].*[1-90].*A",var):
            colvars[i]="$COL_"+re.search(".*A",var).group()[:-1]
        else:
            colvars[i]="COL_"+var

    for var in varsProcess:
        qtype=qtypes[varsProcess.index(var)]
        result+=writeQuestion(var,colvars,qtype,result,includeall=checkinclude)
    return result

def writeAgrupMulti(prefix,listVars,label):
    try:
        txt= "\nMRSETS\n  /MCGROUP NAME=$"+prefix[:-1]+" LABEL='"+str(label) +"'\n    VARIABLES="
        for var in listVars:
            txt+=var+" "
        txt+=".\n"
        return txt
    except:
        return ""

def getCloneCodeVars(spss_file: BytesIO,xlsx_file: BytesIO):
    file_xlsx = get_temp_file(xlsx_file)
    colVars=pd.melt(pd.read_excel(file_xlsx,nrows=2),var_name="colVars",value_name="colVarsNames").drop(0)
    temp_file_name = get_temp_file(spss_file)
    data, study_metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )
    columnVars=colVars.iloc[:,0]
    columnsclone="SPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="
    for col in columnVars:
        if not re.search("^[PFSV].*[1-90].*A",col):
            columnsclone+=col+" "
    columnsclone+="\n/OPTIONS FIX=\"COL_\" FIXTYPE=PREFIX ACTION=RUN.\n"
    for row in range(len(colVars)):
        col =colVars.iloc[row][0]
        if re.search("^[PFSV].*[1-90].*A",col):
            prefix=re.search(".*A",col).group()
            serie=False
            multis=[]
            for var, label in study_metadata.column_names_to_labels.items():
                if re.search(".A",var):
                    if re.search(".*A",var).group()==prefix:
                        serie=True
                        multis.append(var)
                if serie:
                    if not re.search(".A",var) or re.search(".*A",var).group()!=prefix:
                        columnsclone+=writeAgrupMulti("COL_"+prefix,multis,colVars.iloc[row][1])
                        break
    for row in range(len(colVars)):
        if not re.search("^[PFSV].*[1-90].*A",colVars.iloc[row][0]):
            columnsclone+="\nVARIABLE LABELS COL_"+colVars.iloc[row][0]+" '"+colVars.iloc[row][1]+"'."
    return columnsclone

def getInverseCodeVars(inverseVars):
    inverserecodes=""
    for var in inverseVars:
        inverserecodes+="\nRECODE "+var+" (5=1) (4=2) (2=4) (1=5)."
    inverserecodes+="\nEXECUTE."
    return inverserecodes

def getScaleCodeVars(spss_file: BytesIO,scaleVars):
    scalerecodes=""
    try:
        for i in range(len(scaleVars)):
            for num in range(len(scaleVars.iloc[i][1].split())):
                float(scaleVars.iloc[i][1].split()[num])
            scalerecodes+="\nRECODE "+scaleVars.iloc[i][0]
            for num in range(len(scaleVars.iloc[i][1].split())):
                scalerecodes+=" ("+str(num+1)+"="+scaleVars.iloc[i][1].split()[num]+")"
            scalerecodes+="."
        scalerecodes+="\nEXECUTE."
        temp_file_name = get_temp_file(spss_file)
        data, study_metadata = pyreadstat.read_sav(
            temp_file_name,
            apply_value_formats=False
        )
        dictValues=study_metadata.variable_value_labels
        for i in range(len(scaleVars)):
            scalerecodes+="\nVALUE LABELS "+scaleVars.iloc[i][0]
            for num in range(len(scaleVars.iloc[i][1].split())):
                scalerecodes+="\n"+scaleVars.iloc[i][1].split()[num]+" \"("+scaleVars.iloc[i][1].split()[num]+") "+dictValues[scaleVars.iloc[i][0]][num+1]+"\""
            scalerecodes+="."
        return scalerecodes
    except:
        return ""

def getGroupCreateMultisCode(spss_file: BytesIO):
    agrupresult=""
    temp_file_name = get_temp_file(spss_file)
    data, study_metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )
    serie=False
    prefix=""
    multis=[]
    label2=""
    for var, label in study_metadata.column_names_to_labels.items():
        if re.search("^[PFSV].*[1-90].*A",var):
            if not serie:
                multis=[]
                prefix=re.search(".*A",var).group()
                multis.append(var)
                serie=True
            else:
                if re.search(".*A",var).group()==prefix:
                    multis.append(var)
                else:
                    agrupresult+=writeAgrupMulti(prefix,multis,label2)
                    multis=[]
                    prefix=re.search(".*A",var).group()
                    multis.append(var)
        elif serie:
            agrupresult+=writeAgrupMulti(prefix,multis,label2)
            multis=[]
            serie=False
        label2=label
    return agrupresult

def getSegmentCode(spss_file: BytesIO,xlsx_file: BytesIO):
    try:
        temp_file_name = get_temp_file(spss_file)
        data, study_metadata = pyreadstat.read_sav(
            temp_file_name,
            apply_value_formats=False
        )
        file_xlsx = get_temp_file(xlsx_file)
        varsList=pd.read_excel(file_xlsx,usecols="M",skiprows=3,names=["varsSegment"]).dropna()["varsSegment"].tolist()
        varsList_segment=pd.read_excel(file_xlsx,usecols="N",skiprows=3,names=["vars_Segment"]).dropna()["vars_Segment"].tolist()

        filterdatabase=""
        namedatasetspss="ConjuntoDatos1"
        if not varsList_segment:
            for var in varsList:
                refdict=study_metadata.variable_value_labels[var]
                refs_unique=data[var].dropna().unique()
                refs_unique.sort()
                for refindex in refs_unique:
                    filterdatabase+="DATASET ACTIVATE "+ namedatasetspss+".\n"
                    filterdatabase+="DATASET COPY REF_"+re.sub("[()\-+áéíóú]","",refdict[refindex].replace(" ","_"))+".\nDATASET ACTIVATE REF_"+re.sub("[()\-+áéíóú]","",refdict[refindex].replace(" ","_"))+".\nFILTER OFF.\nUSE ALL.\n"
                    filterdatabase+="SELECT IF ("+var+" = "+str(int(refindex))+").\nEXECUTE.\n\n"
        else:
            for var_segment in varsList_segment:
                refdict_segment=study_metadata.variable_value_labels[var_segment]
                refs_segment_unique=data[var_segment].dropna().unique()
                refs_segment_unique.sort()
                for refindex_segment in refs_segment_unique:
                    name_var_segment=re.sub("[()\-+áéíóú]","",refdict_segment[refindex_segment].replace(" ","_"))
                    for var in varsList:
                        refdict=study_metadata.variable_value_labels[var]
                        refs_unique=data[var].dropna().unique()
                        refs_unique.sort()
                        for refindex in refs_unique:
                            name_var=re.sub("[()\-+áéíóú]","",refdict[refindex].replace(" ","_"))
                            name_dataset=name_var+"_"+name_var_segment
                            filterdatabase+="DATASET ACTIVATE "+ namedatasetspss+".\n"
                            filterdatabase+="DATASET COPY REF_"+name_dataset+".\nDATASET ACTIVATE REF_"+name_dataset+".\nFILTER OFF.\nUSE ALL.\n"
                            filterdatabase+="SELECT IF ("+var+" = "+str(int(refindex))+" AND "+var_segment+" = "+str(int(refindex_segment))+").\nEXECUTE.\n\n"
        return filterdatabase
    except:
        return "References variable not is REF.1"

def writeQuestion(varName,qtype, colVars,descendingorder=False,includeall=False, varanidada=""):
    txt=""
    if qtype=="M":
        varName="$"+re.search(".*A",varName).group()[:-1]
    txt+="\nCTABLES\n  /VLABELS VARIABLES="+varName+" TOTAL "
    for colvar in colVars:
        txt+=colvar +" "
    txt+="DISPLAY=LABEL"
    if qtype in ["E","J"]:
        txt+=("\n  /PCOMPUTE &cat1 = EXPR([4]+[5])"
            + "\n  /PPROPERTIES &cat1 LABEL = \"NETO TOP TWO BOX\" FORMAT=COUNT '1' F40.0 HIDESOURCECATS=NO"
            + "\n  /PCOMPUTE &cat2 = EXPR([2]+[1])\n  /PPROPERTIES &cat2 LABEL = \"NETO BOTTOM TWO BOX\" FORMAT=COUNT '1' F40.0 HIDESOURCECATS=NO")

    txt+="\n  /TABLE "+varName+" [C][COUNT '1' F40.0, TOTALS["
    if qtype in ["E","N"]:
        txt+="MEAN 'Promedio:' F40.2, STDDEV 'Desviación estándar:' F40.2, SEMEAN 'Error estándar:' F40.2,\n"
    if qtype in["M"]:
        txt+="COUNT 'Total' F40.0, RESPONSES 'Total Respuestas' F40.0, COLPCT.RESPONSES.COUNT '%' F40.0]] BY "
    else:
        txt+="COUNT 'Total' F40.0, TOTALN 'Total Respuestas' F40.0, COLPCT.COUNT '%' F40.0]] BY "
    if varanidada!="":
        txt+=varanidada+" > ("
    txt+="TOTAL[C]"
    for colvar in colVars:
        txt+= " + "+colvar+" [C]"
    if varanidada!="":
        txt+=")"
    txt+="\n  /SLABELS POSITION=ROW\n  /CATEGORIES VARIABLES="+varName
    if qtype in ["E","J"]:
        txt+=" [&cat1, 5, 4, 3, 2, 1, &cat2] "
    elif qtype in ["M"]:
        txt+=" ORDER=D KEY=COUNT "
    elif descendingorder:
        txt+=" ORDER=D KEY=VALUE "
    else:
        txt+=" ORDER=A KEY=VALUE "

    if qtype in ["E","J"]:
        txt+="EMPTY=INCLUDE TOTAL=YES POSITION=AFTER"
    else:
        txt+="EMPTY=EXCLUDE TOTAL=YES POSITION=AFTER"

    txt+="\n  /CATEGORIES VARIABLES=TOTAL "
    if varanidada!="":
        txt+=varanidada+" "
    for colvar in colVars:
        txt+= colvar+" "
    if includeall:
        txt+="ORDER=A EMPTY=INCLUDE"
    else:
        txt+="ORDER=A EMPTY=EXCLUDE"

    txt+=("\n  /CRITERIA CILEVEL=95\n  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN INCLUDEMRSETS=YES"
        + "\n  CATEGORIES=SUBTOTALS MERGE=YES STYLE=SIMPLE SHOWSIG=NO.\n")
    return txt

def writeAbiertasQuestion(varName,colVars,orderlist,includeall=False,varanidada=""):
    txt=""
    varName="$"+re.search(".*A",varName).group()[:-1]
    txt+="\nCTABLES\n  /VLABELS VARIABLES="+varName+" TOTAL "
    for colvar in colVars:
        txt+=colvar +" "
    txt+="DISPLAY=LABEL\n  /TABLE "+varName+" [C][COUNT '1' F40.0, TOTALS["
    txt+="COUNT 'Total' F40.0, RESPONSES 'Total Respuestas' F40.0, COLPCT.RESPONSES.COUNT '%' F40.0]] BY "
    if varanidada!="":
        txt+=varanidada+" > ("
    txt+="TOTAL[C]"
    for colvar in colVars:
        txt+= " + "+colvar+" [C]"
    if varanidada!="":
        txt+=")"
    txt+="\n  /SLABELS POSITION=ROW\n  /CATEGORIES VARIABLES="+varName
    txt+=" ["+", ".join(str(x) for x in orderlist)+"] "
    txt+="EMPTY=INCLUDE TOTAL=YES POSITION=AFTER"
    txt+="\n  /CATEGORIES VARIABLES=TOTAL "
    if varanidada!="":
        txt+=varanidada+" "
    for colvar in colVars:
        txt+= colvar+" "
    if includeall:
        txt+="ORDER=A EMPTY=INCLUDE"
    else:
        txt+="ORDER=A EMPTY=EXCLUDE"
    txt+=("\n  /CRITERIA CILEVEL=95\n  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN INCLUDEMRSETS=YES"
        + "\n  CATEGORIES=SUBTOTALS MERGE=YES STYLE=SIMPLE SHOWSIG=NO.\n")
    return txt
