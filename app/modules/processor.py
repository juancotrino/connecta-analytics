from collections import Counter
from io import BytesIO
import re
import pandas as pd
import numpy as np
import math
import tempfile
from app.modules.segment_spss import get_temp_file
from app.modules.text_function import processSavMulti
from openpyxl import Workbook, load_workbook
from difflib import SequenceMatcher
from openpyxl.cell.text import InlineFont
from openpyxl.cell.rich_text import TextBlock, CellRichText
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import PatternFill, Border, Side, Alignment, Protection, Font

import pyreadstat

def getPreProcessCode(spss_file: BytesIO,xlsx_file: BytesIO):
    file_xlsx = get_temp_file(xlsx_file)
    inverseVarsList=pd.read_excel(file_xlsx,usecols="A,E",skiprows=3,names=["vars","inverses"]).dropna()
    inverseVarsList=inverseVarsList[inverseVarsList["inverses"]=="I"].iloc[:,0]
    scaleVarsList=pd.read_excel(file_xlsx,usecols="A,D",skiprows=3,names=["vars","scale"]).dropna()

    preprocesscode=""
    preprocesscode+=processSavMulti(spss_file)[1]+processSavMulti(spss_file)[0]
    preprocesscode+=getGroupCreateMultisCode(spss_file)
    if not inverseVarsList.empty:
        preprocesscode+=getInverseCodeVars(spss_file,inverseVarsList)
    if not scaleVarsList.empty:
        preprocesscode+=getScaleCodeVars(spss_file,scaleVarsList)
    preprocesscode+="\nCOMPUTE TOTAL=1.\nVARIABLE LABELS TOTAL 'TOTAL'.\nVALUE LABELS TOTAL 1 \"TOTAL\".\nEXECUTE.\n"
    preprocesscode+=getCloneCodeVars(spss_file,xlsx_file)
    preprocesscode+=getPreProcessAbiertas(spss_file,xlsx_file)
    return preprocesscode

def checkPreProcessCodeUnique(spss_file: BytesIO,xlsx_file: BytesIO):
    file_xlsx = get_temp_file(xlsx_file)
    inverseVarsList=pd.read_excel(file_xlsx,usecols="A,E",skiprows=3,names=["vars","inverses"]).dropna()
    inverseVarsList=inverseVarsList[inverseVarsList["inverses"]=="I"].iloc[:,0]
    scaleVarsList=pd.read_excel(file_xlsx,usecols="A,D",skiprows=3,names=["vars","scale"]).dropna()
    flag1=False
    flag2=False
    if not inverseVarsList.empty:
        flag1=checkInverseCodeVars(spss_file,inverseVarsList)
    if not scaleVarsList.empty:
        flag2=getScaleCodeVars(spss_file,scaleVarsList)!=""
    return flag1,flag2

def getPreProcessCode2(spss_file: BytesIO):
    preprocesscode=processSavMulti(spss_file)[1]+processSavMulti(spss_file)[0]
    return preprocesscode


def getProcessCode2(spss_file: BytesIO,xlsx_file: BytesIO,checkinclude=False,rutaarchivo=""):
    result,warning2=getProcessCode(spss_file,xlsx_file,checkinclude)
    file_xlsx = get_temp_file(xlsx_file)
    nombrehoja=pd.read_excel(file_xlsx,usecols="O",skiprows=3,names=["name"]).dropna().iloc[0,0]
    try:
        sufijo=pd.read_excel(file_xlsx,usecols="P",skiprows=3,names=["name"]).dropna().iloc[0,0]
        sufijo=" "+str(sufijo)
    except:
        sufijo=""
    warning=""
    if warning2!="":
        warning+="/"+nombrehoja+"/ "+warning2
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
                result_preg,_=getProcessCode(spss_file,xlsx_file,checkinclude,condition=condition)
                result+=result_preg
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
                            result_preg,_=getProcessCode(spss_file,xlsx_file,checkinclude,condition=condition)
                            result+=result_preg
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
    return result, warning

def getProcessCode(spss_file: BytesIO,xlsx_file: BytesIO,checkinclude=False,condition=None):

    file_xlsx = get_temp_file(xlsx_file)
    varsList=pd.read_excel(file_xlsx,usecols="A,B,D,E",skiprows=3,names=["vars","varsTypes","Scales","descendOrder"]).dropna(subset=["vars"])
    colVarsList=pd.melt(pd.read_excel(file_xlsx,nrows=2),var_name="colVars",value_name="colVarsNames").drop(0)
    result=""
    warning=""
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
            if varsList.iloc[i][3]!="D" and varsList.iloc[i][3]!="P":
                result+=writeQuestion(varsList.iloc[i][0],varsList.iloc[i][1],colvars,includeall=checkinclude)
            elif varsList.iloc[i][3]=="P":
                result+=writeQuestion(varsList.iloc[i][0],varsList.iloc[i][1],colvars,includeall=checkinclude,custom_order=varsList.iloc[i][2])
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
            result_abierta,result_warning=getProcessAbiertas(spss_file,xlsx_file,checkinclude,varsList.iloc[i][0],condition=condition)
            result+=result_abierta
            warning+=result_warning
    return result,warning


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
            try:
                if study_metadata.column_names_to_labels[multi].lower().startswith("otro"):
                    delmultis.append(multi)
            except:
                continue
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
        abiertascode+="\n"+str(num).strip()+" \""+str(option).strip()+"\""
    abiertascode+=".\nEXECUTE.\n"
    return abiertascode

def getProcessAbiertas(spss_file: BytesIO,xlsx_file: BytesIO,checkinclude=False,namevar="",condition=None):
    result=""
    warning=""
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
            lista_codigos=[]
            lista_final_codigos=[]
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
                lista_final_codigos.append(lcTable.iloc[j][0])

            lcTable2=pd.read_excel(file_xlsx,sheet_name=varsList.iloc[i][1],usecols="A,B",skiprows=1,names=["vars","sheetNames"])
            for j in range(len(lcTable2)):
                lista_codigos.append(lcTable2.iloc[j][0])

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

            flag_preginclude=True
            flag_preginclude2=True

            for cod in count:
                if not cod in lista_final_codigos and flag_preginclude2:
                    warning+= "#Code without label in " + prefix+"# "
                    flag_preginclude2=False
                if not cod in lista_codigos:
                    if flag_preginclude:
                        warning+="\nCode Missing in "+prefix+" : "
                        flag_preginclude=False
                    warning+=str(cod)+" | "

            listatotaluniq=list(set(listatotal))
            for net in listNetos:
                if net[0]!="First" and net[0]!="End" and any(count[ele]>0 for ele in net[1]):
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
    return result , warning

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

def writeAgrupMulti(prefix,listVars,label):
    try:
        if len(listVars)>1:
            txt= "\nMRSETS\n  /MCGROUP NAME=$"+prefix[:-1]+" LABEL='"+str(label) +"'\n    VARIABLES="
            for var in listVars:
                txt+=var+" "
            txt+=".\n"
            return txt
        return ""
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

    columnsclone="\nDELETE VARIABLES"
    for col in columnVars:
        if not re.search("^[PFSV].*[1-90].*A",col):
            columnsclone+=" COL_"+col
    columnsclone+=".\nEXECUTE.\n"
    columnsclone+="SPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="
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

def getInverseCodeVars(spss_file: BytesIO,inverseVars):
    temp_file_name = get_temp_file(spss_file)
    data, study_metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )
    dictValues=study_metadata.variable_value_labels
    inverserecodes=""
    inverserecodes="\nSPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="
    for var in inverseVars:
        inverserecodes+=var+" "
    inverserecodes+="\n/OPTIONS FIX=\"BACKUP_INVERSE_\" FIXTYPE=PREFIX ACTION=RUN.\n"
    for var in inverseVars:
        if not re.search("^\([0-9]\).*",dictValues[var][1]):
            inverserecodes+="\nRECODE "+var+" (5=1) (4=2) (2=4) (1=5)."
            inverserecodes+="\nVALUE LABELS "+var
            for i in range(1,6):
                inverserecodes+="\n"+str(i)+" \"("+str(i)+") "+dictValues[var][6-i]+"\""
            inverserecodes+="."
    inverserecodes+="\nEXECUTE."
    return inverserecodes

def checkInverseCodeVars(spss_file: BytesIO,inverseVars):
    temp_file_name = get_temp_file(spss_file)
    data, study_metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )
    dictValues=study_metadata.variable_value_labels
    inverserecodes=""
    inverserecodes="\nSPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="
    for var in inverseVars:
        inverserecodes+=var+" "
    inverserecodes+="\n/OPTIONS FIX=\"BACKUP_INVERSE_\" FIXTYPE=PREFIX ACTION=RUN.\n"
    for var in inverseVars:
        if not re.search("^\([0-9]\).*",dictValues[var][1]):
            return True
    return False

def getScaleCodeVars(spss_file: BytesIO,scaleVars):
    scalerecodes=""
    try:
        temp_file_name = get_temp_file(spss_file)
        data, study_metadata = pyreadstat.read_sav(
            temp_file_name,
            apply_value_formats=False
        )
        dictValues=study_metadata.variable_value_labels
        scalerecodes="\nSPSS_TUTORIALS_CLONE_VARIABLES VARIABLES="
        for i in range(len(scaleVars)):
            scalerecodes+=scaleVars.iloc[i][0]+" "
        scalerecodes+="\n/OPTIONS FIX=\"BACKUP_SCALE_\" FIXTYPE=PREFIX ACTION=RUN.\n"
        scalecodeback=scalerecodes

        for i in range(len(scaleVars)):
            scalecode1=""
            try:
                for num in range(len(scaleVars.iloc[i][1].split())):
                    float(scaleVars.iloc[i][1].split()[num])
                for num in range(len(scaleVars.iloc[i][1].split())):
                    "\n"+scaleVars.iloc[i][1].split()[num]+" \"("+scaleVars.iloc[i][1].split()[num]+") "+dictValues[scaleVars.iloc[i][0]][num+1]+"\""
                scalecode1+="\nRECODE "+scaleVars.iloc[i][0]
                for num in range(len(scaleVars.iloc[i][1].split())):
                    scalecode1+=" ("+str(num+1)+"="+scaleVars.iloc[i][1].split()[num]+")"
                scalecode1+="."
            except:
                scalecode1=""
            scalerecodes+=scalecode1
        if scalerecodes==scalecodeback:
            return ""
        scalerecodes+="\nEXECUTE."

        for i in range(len(scaleVars)):
            try:
                scalecode2=""
                for num in range(len(scaleVars.iloc[i][1].split())):
                        float(scaleVars.iloc[i][1].split()[num])
                scalecode2+="\nVALUE LABELS "+scaleVars.iloc[i][0]
                for num in range(len(scaleVars.iloc[i][1].split())):
                    scalecode2+="\n"+scaleVars.iloc[i][1].split()[num]+" \"("+scaleVars.iloc[i][1].split()[num]+") "+dictValues[scaleVars.iloc[i][0]][num+1]+"\""
                scalecode2+="."
            except:
                scalecode2=""
            scalerecodes+=scalecode2
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
        return "Error with Variables to segment"

def writeQuestion(varName,qtype, colVars,descendingorder=False,includeall=False, varanidada="",custom_order=""):
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
    if custom_order !="":
        txt+=" "+custom_order+" "
    elif qtype in ["E","J"]:
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

def write_temp_excel(wb):
    with tempfile.NamedTemporaryFile() as tmpfile:
        # Write the DataFrame to the temporary SPSS file
        wb.save(tmpfile.name)

        with open(tmpfile.name, 'rb') as f:
            return BytesIO(f.read())

def getVarsForPlantilla(spss_file: BytesIO):
    temp_file_name = get_temp_file(spss_file)
    data, study_metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )
    dict_values=study_metadata.variable_value_labels
    list_vars=study_metadata.column_names
    n_total=study_metadata.number_rows
    var_type_base=study_metadata.original_variable_types#F-- Float / A-- String
    # Create a new Workbook
    wb_new = Workbook()
    # Remove the default sheet created with the new workbook
    default_sheet = wb_new.active
    wb_new.remove(default_sheet)

    ws_plantilla = wb_new.create_sheet(title="Estadisticas Plantilla")

    redFill = PatternFill(start_color='C80000',
                   end_color='C80000',
                   fill_type='solid')

    yellowFill = PatternFill(start_color='FFFF00',
            end_color='FFFF00',
            fill_type='solid')

    blueFill = PatternFill(start_color='C5D9F1',
            end_color='C5D9F1',
            fill_type='solid')

    greenFillTitle = PatternFill(start_color='70AD47',
            end_color='70AD47',
            fill_type='solid')

    medium_border = Border(left=Side(style='medium'),
                     right=Side(style='medium'),
                     top=Side(style='medium'),
                     bottom=Side(style='medium'))

    ws_plantilla.cell(row=1,column=1).value="Variable"
    ws_plantilla.cell(row=1,column=2).value="Tipo de Variable"
    ws_plantilla.cell(row=1,column=3).value="NValids"
    ws_plantilla.cell(row=1,column=4).value="Unique Distinct Values"
    ws_plantilla.cell(row=1,column=5).value="Total Options Values"
    ws_plantilla.cell(row=1,column=6).value="Option 5"

    for col in range(1,7):
        ws_plantilla.cell(row=1,column=col).fill=greenFillTitle
        ws_plantilla.cell(row=1,column=col).font = Font(color = "FFFFFF")
        ws_plantilla.cell(row=1,column=col).border = medium_border
        column_letter = get_column_letter(col)
        if col==1:
            width_col=22
        else:
            width_col=7
        ws_plantilla.column_dimensions[column_letter].width = width_col

    ws_plantilla.auto_filter.ref = ws_plantilla.dimensions

    textPlantilla="Variable\tTipo de Variable\tNValids\tUnique Values"
    multis=[]
    row_num=2

    vars_to_ignore=["s1","s2","Response_ID","IMAGEN","MARCA","PRECIO","TelA","N.encuesta","tipo_super","ABIERTAS","ETIQUETAS","tipo.super","Tel.","N.enc.","tipo.","acabado."]
    for var in list_vars:

        if var_type_base[var].startswith("A") or any(var.lower().startswith(ignore.lower()) for ignore in vars_to_ignore):
            continue
        if re.search("^[FPS].*A.*[1-90]",var):
            group_multi=re.search(".*A",var).group()
            if group_multi in multis:
                continue
            multis.append(group_multi)

            textPlantilla+="\n"+var+"\t"
            ws_plantilla.cell(row=row_num,column=1).value=var
            try:
                dict_values[var]
                textPlantilla+="M\t"
                ws_plantilla.cell(row=row_num,column=2).value="M"
            except:
                textPlantilla+="A\t"
                ws_plantilla.cell(row=row_num,column=2).value="A"
            index_list=[]
            count_unique=0
            count_total=0
            for var2 in list_vars:
                if re.search(group_multi,var2):
                    count_total+=1
                    if len(data[var2].dropna().index.tolist())!=0:
                        count_unique+=1
                    for ind in data[var2].dropna().index.tolist():
                        index_list.append(ind)
            textPlantilla+=str(len(list(set(index_list))))+"\t"+str(count_unique)+"|"+str(count_total)
            ws_plantilla.cell(row=row_num,column=3).value=str(len(list(set(index_list))))
            if ws_plantilla.cell(row=row_num,column=3).value != str(n_total):
                ws_plantilla.cell(row=row_num,column=3).fill=yellowFill
            if ws_plantilla.cell(row=row_num,column=3).value == "0":
                ws_plantilla.cell(row=row_num,column=3).fill=redFill
            ws_plantilla.cell(row=row_num,column=4).value=str(count_unique)+"|"+str(count_total)
            if ws_plantilla.cell(row=row_num,column=4).value=="1|1":
                ws_plantilla.cell(row=row_num,column=4).fill=yellowFill
        else:
            textPlantilla+="\n"+var+"\t"
            ws_plantilla.cell(row=row_num,column=1).value=var
            try:
                if len(dict_values[var])==5:
                    if "just" in dict_values[var][3] or "Just" in dict_values[var][3]:
                        textPlantilla+="J\t"
                        ws_plantilla.cell(row=row_num,column=2).value="J"
                    else:
                        textPlantilla+="E\t"
                        ws_plantilla.cell(row=row_num,column=2).value="E"
                        if not "5" in dict_values[var][5]:
                            ws_plantilla.cell(row=row_num,column=6).value="not 5"
                            ws_plantilla.cell(row=row_num,column=6).fill=yellowFill
                elif dict_values[var][1]=="":
                    textPlantilla+="N\t"
                    ws_plantilla.cell(row=row_num,column=2).value="N"
                else:
                    textPlantilla+="U\t"
                    ws_plantilla.cell(row=row_num,column=2).value="U"
            except:
                textPlantilla+="U\t"
                ws_plantilla.cell(row=row_num,column=2).value="U"
            textPlantilla+=str(len(data[var].dropna()))+"\t"
            ws_plantilla.cell(row=row_num,column=3).value=str(len(data[var].dropna()))
            if ws_plantilla.cell(row=row_num,column=3).value != str(n_total):
                ws_plantilla.cell(row=row_num,column=3).fill=yellowFill
            if ws_plantilla.cell(row=row_num,column=3).value == "0":
                ws_plantilla.cell(row=row_num,column=3).fill=redFill

            ws_plantilla.cell(row=row_num,column=4).value=str(len(list(set(data[var].dropna()))))
            if ws_plantilla.cell(row=row_num,column=4).value=="1":
                ws_plantilla.cell(row=row_num,column=4).fill=yellowFill

            try:
                textPlantilla+=str(len(list(set(data[var].dropna()))))+"\t/"+str(len(dict_values[var]))
                ws_plantilla.cell(row=row_num,column=5).value="/"+str(len(dict_values[var]))
            except:
                textPlantilla+=str(len(list(set(data[var].dropna()))))+"\t/--"
                ws_plantilla.cell(row=row_num,column=5).value="/--"
        row_num+=1
    return textPlantilla , write_temp_excel(wb_new)

def get_comparison_tables(spss_file1: BytesIO,spss_file2: BytesIO):
    # Create a new Workbook
    wb_new = Workbook()
    # Remove the default sheet created with the new workbook
    default_sheet = wb_new.active
    wb_new.remove(default_sheet)
    for caso in range(2):
        ws_plantilla = wb_new.create_sheet(title="Estadisticas Plantilla "+str(caso+1))
        if caso==0:
            archivo1=spss_file1
            archivo2=spss_file2
        else:
            archivo1=spss_file2
            archivo2=spss_file1
        temp_file_name = get_temp_file(archivo1)
        data, study_metadata = pyreadstat.read_sav(
            temp_file_name,
            apply_value_formats=False
        )
        temp_file_name2 = get_temp_file(archivo2)
        data2, study_metadata2 = pyreadstat.read_sav(
            temp_file_name2,
            apply_value_formats=False
        )

        dict_values=study_metadata.variable_value_labels
        list_vars=study_metadata.column_names
        dict_values2=study_metadata2.variable_value_labels
        list_vars2=study_metadata2.column_names
        n_total=study_metadata.number_rows
        var_type_base=study_metadata.original_variable_types#F-- Float / A-- String

        dict_labels=study_metadata.column_names_to_labels
        dict_labels2=study_metadata2.column_names_to_labels

        redFill = PatternFill(start_color='C80000',
                    end_color='C80000',
                    fill_type='solid')

        yellowFill = PatternFill(start_color='FFFF00',
                end_color='FFFF00',
                fill_type='solid')

        blueFill = PatternFill(start_color='C5D9F1',
                end_color='C5D9F1',
                fill_type='solid')

        grayFill = PatternFill(start_color='DBDBDB',
                end_color='DBDBDB',
                fill_type='solid')

        greenFillTitle = PatternFill(start_color='70AD47',
                end_color='70AD47',
                fill_type='solid')

        medium_border = Border(left=Side(style='medium'),
                        right=Side(style='medium'),
                        top=Side(style='medium'),
                        bottom=Side(style='medium'))
        green_thin_border = Border(
                        left=Side(border_style="thin", color="F7F9F1"),
                        right=Side(border_style="thin", color="F7F9F1"),
                        top=Side(border_style="thin", color="F7F9F1"),
                        bottom=Side(border_style="thin", color="F7F9F1"))
        greenBackground = PatternFill(start_color='EBF1DE',
                end_color='EBF1DE',
                fill_type='solid')
        blueBackground = PatternFill(start_color='DCE6F1',
                end_color='DCE6F1',
                fill_type='solid')

        ws_plantilla.cell(row=1,column=1).value="Variable"
        ws_plantilla.cell(row=1,column=2).value="Tipo de Variable"
        ws_plantilla.cell(row=1,column=3).value="NValids"
        ws_plantilla.cell(row=1,column=4).value="Unique Distinct Values"
        ws_plantilla.cell(row=1,column=5).value="Total Options Values"
        ws_plantilla.cell(row=1,column=6).value="Option 5"
        ws_plantilla.cell(row=1,column=7).value="Var in other Base"
        ws_plantilla.cell(row=1,column=8).value="Same Value labels"
        ws_plantilla.cell(row=1,column=9).value="Labels Base 1"
        ws_plantilla.cell(row=1,column=10).value="Labels Base 2"
        ws_plantilla.cell(row=1,column=11).value="T. Rate Options"
        ws_plantilla.cell(row=1,column=12).value="Same label"
        ws_plantilla.cell(row=1,column=13).value="Label 1"
        ws_plantilla.cell(row=1,column=14).value="Label 2"
        ws_plantilla.cell(row=1,column=15).value="Similar Rate"
        ws_plantilla.cell(row=1,column=16).value=archivo1.name
        ws_plantilla.cell(row=1,column=17).value=archivo2.name

        # for row in range(2,len(list_vars)+1):
        #     for col in range(1,16):
        #         if col in [7,8,9,12,13,17]:
        #             fillcol=blueBackground
        #             bordercol=blue_thin_border
        #         else:
        #             fillcol=greenBackground
        #             bordercol=green_thin_border
        #         ws_plantilla.cell(row=row,column=col).fill=fillcol
        #         ws_plantilla.cell(row=row,column=col).border=bordercol

        for col in range(1,18):
            if col in [7,8,9,12,13,17]:
                fillcol=blueFill
            else:
                fillcol=greenFillTitle
            ws_plantilla.cell(row=1,column=col).fill=fillcol
            ws_plantilla.cell(row=1,column=col).font = Font(color = "FFFFFF")
            ws_plantilla.cell(row=1,column=col).border = medium_border
            column_letter = get_column_letter(col)
            if col in[1]:
                width_col=22
            elif col in[11]:
                width_col=9
            elif col in [16,17]:
                width_col=50
            else:
                width_col=7
            ws_plantilla.column_dimensions[column_letter].width = width_col

        ws_plantilla.auto_filter.ref = ws_plantilla.dimensions

        multis=[]
        row_num=2

        vars_to_ignore=["s1","s2","Response_ID","IMAGEN","MARCA","PRECIO","TelA","N.encuesta","tipo_super","ABIERTAS","ETIQUETAS","tipo.super","Tel.","N.enc.","tipo.","acabado."]
        for var in list_vars:

            if var_type_base[var].startswith("A") or any(var.lower().startswith(ignore.lower()) for ignore in vars_to_ignore):
                continue
            if re.search("^[FPS].*A.*[1-90]",var):
                group_multi=re.search(".*A",var).group()
                if group_multi in multis:
                    continue
                multis.append(group_multi)

                ws_plantilla.cell(row=row_num,column=1).value=var
                try:
                    dict_values[var]
                    ws_plantilla.cell(row=row_num,column=2).value="M"
                except:
                    ws_plantilla.cell(row=row_num,column=2).value="A"
                index_list=[]
                count_unique=0
                count_total=0
                for var2 in list_vars:
                    if re.search(group_multi,var2):
                        count_total+=1
                        if len(data[var2].dropna().index.tolist())!=0:
                            count_unique+=1
                        for ind in data[var2].dropna().index.tolist():
                            index_list.append(ind)
                count_total2=0
                for var3 in list_vars2:
                    if re.search(group_multi,var3):
                        count_total2+=1
                ws_plantilla.cell(row=row_num,column=3).value=str(len(list(set(index_list))))
                if ws_plantilla.cell(row=row_num,column=3).value != str(n_total):
                    ws_plantilla.cell(row=row_num,column=3).fill=yellowFill
                if ws_plantilla.cell(row=row_num,column=3).value == "0":
                    ws_plantilla.cell(row=row_num,column=3).fill=redFill
                ws_plantilla.cell(row=row_num,column=4).value=str(count_unique)+"|"+str(count_total)
                if ws_plantilla.cell(row=row_num,column=4).value=="1|1":
                    ws_plantilla.cell(row=row_num,column=4).fill=yellowFill
                if var in list_vars2:
                    ws_plantilla.cell(row=row_num,column=7).value=var
                    try:
                        labelval1=dict_values[var]
                    except:
                        labelval1=""
                    try:
                        labelval2=dict_values2[var]
                    except:
                        labelval2=""
                    label_base1=dict_labels[var]
                    label_base2=dict_labels2[var]
                    if(labelval1==labelval2) and (count_total==count_total2):
                        ws_plantilla.cell(row=row_num,column=8).value="Yes"
                    elif (labelval1==labelval2) and (count_total!=count_total2):
                        ws_plantilla.cell(row=row_num,column=8).value="Same Labels"
                        ws_plantilla.cell(row=row_num,column=8).fill=yellowFill
                        ws_plantilla.cell(row=row_num,column=9).value="Distint number of variables in multiple"
                        ws_plantilla.cell(row=row_num,column=10).value=str(count_total2)+" | "+str(count_total)
                    else:
                        ws_plantilla.cell(row=row_num,column=8).value="No"
                        ws_plantilla.cell(row=row_num,column=8).fill=redFill
                        ws_plantilla.cell(row=row_num,column=9).value=str(labelval2)
                        ws_plantilla.cell(row=row_num,column=9).fill=grayFill
                        ws_plantilla.cell(row=row_num,column=7).fill=grayFill
                        ws_plantilla.cell(row=row_num,column=10).value=str(labelval1)
                        ws_plantilla.cell(row=row_num,column=11).value=str(len(labelval2))+"|"+str(len(labelval1)) +"--"+'{0:.0%}'.format(SequenceMatcher(None, str(labelval2).lower(), str(labelval1).lower()).ratio())
                    if(label_base1==label_base2):
                        ws_plantilla.cell(row=row_num,column=12).value="Yes"
                    else:
                        ws_plantilla.cell(row=row_num,column=12).value="No"
                        ws_plantilla.cell(row=row_num,column=12).fill=blueFill
                        ws_plantilla.cell(row=row_num,column=13).value=str(label_base2)
                        ws_plantilla.cell(row=row_num,column=13).fill=grayFill
                        ws_plantilla.cell(row=row_num,column=7).fill=grayFill
                        ws_plantilla.cell(row=row_num,column=14).value=str(label_base1)
                        ws_plantilla.cell(row=row_num,column=15).value='{0:.0%}'.format(SequenceMatcher(None, str(label_base2).lower(), str(label_base1).lower()).ratio())
                else:
                    ws_plantilla.cell(row=row_num,column=7).value="No"
                    ws_plantilla.cell(row=row_num,column=7).fill=blueFill
            else:
                ws_plantilla.cell(row=row_num,column=1).value=var
                try:
                    if len(dict_values[var])==5:
                        if "just" in dict_values[var][3] or "Just" in dict_values[var][3]:
                            ws_plantilla.cell(row=row_num,column=2).value="J"
                        else:
                            ws_plantilla.cell(row=row_num,column=2).value="E"
                            if not "5" in dict_values[var][5]:
                                ws_plantilla.cell(row=row_num,column=6).value="not 5"
                                ws_plantilla.cell(row=row_num,column=6).fill=yellowFill
                    elif dict_values[var][1]=="":
                        ws_plantilla.cell(row=row_num,column=2).value="N"
                    else:
                        ws_plantilla.cell(row=row_num,column=2).value="U"
                except:
                    ws_plantilla.cell(row=row_num,column=2).value="U"
                ws_plantilla.cell(row=row_num,column=3).value=str(len(data[var].dropna()))
                if ws_plantilla.cell(row=row_num,column=3).value != str(n_total):
                    ws_plantilla.cell(row=row_num,column=3).fill=yellowFill
                if ws_plantilla.cell(row=row_num,column=3).value == "0":
                    ws_plantilla.cell(row=row_num,column=3).fill=redFill

                ws_plantilla.cell(row=row_num,column=4).value=str(len(list(set(data[var].dropna()))))
                if ws_plantilla.cell(row=row_num,column=4).value=="1":
                    ws_plantilla.cell(row=row_num,column=4).fill=yellowFill
                try:
                    ws_plantilla.cell(row=row_num,column=5).value="/"+str(len(dict_values[var]))
                except:
                    ws_plantilla.cell(row=row_num,column=5).value="/--"
                if var in list_vars2:
                    ws_plantilla.cell(row=row_num,column=7).value=var
                    try:
                        labelval1=dict_values[var]
                    except:
                        labelval1=""
                    try:
                        labelval2=dict_values2[var]
                    except:
                        labelval2=""

                    label_base1=dict_labels[var]
                    label_base2=dict_labels2[var]

                    if(labelval1==labelval2):
                        ws_plantilla.cell(row=row_num,column=8).value="Yes"
                    else:
                        ws_plantilla.cell(row=row_num,column=8).value="No"
                        ws_plantilla.cell(row=row_num,column=8).fill=redFill
                        ws_plantilla.cell(row=row_num,column=9).value=str(labelval2)
                        ws_plantilla.cell(row=row_num,column=9).fill=grayFill
                        ws_plantilla.cell(row=row_num,column=7).fill=grayFill
                        ws_plantilla.cell(row=row_num,column=10).value=str(labelval1)
                        ws_plantilla.cell(row=row_num,column=11).value=str(len(labelval2))+"|"+str(len(labelval1))+"--"+'{0:.0%}'.format(SequenceMatcher(None, str(labelval2).lower(), str(labelval1).lower()).ratio())
                    if(label_base1==label_base2):
                        ws_plantilla.cell(row=row_num,column=12).value="Yes"
                    else:
                        ws_plantilla.cell(row=row_num,column=12).value="No"
                        ws_plantilla.cell(row=row_num,column=12).fill=blueFill
                        ws_plantilla.cell(row=row_num,column=13).value=str(label_base2)
                        ws_plantilla.cell(row=row_num,column=13).fill=grayFill
                        ws_plantilla.cell(row=row_num,column=7).fill=grayFill
                        ws_plantilla.cell(row=row_num,column=14).value=str(label_base1)
                        ws_plantilla.cell(row=row_num,column=15).value='{0:.0%}'.format(SequenceMatcher(None, str(label_base2).lower(), str(label_base1).lower()).ratio())
                else:
                    ws_plantilla.cell(row=row_num,column=7).value="No"
                    ws_plantilla.cell(row=row_num,column=7).fill=blueFill
            row_num+=1

    return write_temp_excel(wb_new)
