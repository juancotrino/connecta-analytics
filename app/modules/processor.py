from io import BytesIO
import re
import pandas as pd
from app.modules.segment_spss import get_temp_file
from app.modules.text_function import processSavMulti
import pyreadstat

def getPreProcessCode(spss_file: BytesIO,xlsx_file: BytesIO):
    file_xlsx = get_temp_file(xlsx_file)
    varsList=pd.read_excel(file_xlsx,usecols="A,B",skiprows=3,names=["vars","varsTypes"])
    colVarsList=pd.melt(pd.read_excel(file_xlsx,nrows=2),var_name="colVars",value_name="colVarsNames").drop(0)
    inverseVarsList=pd.read_excel(file_xlsx,usecols="A,C",skiprows=3,names=["vars","inverses"]).dropna().iloc[:,0]
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
    return preprocesscode

def getProcessCode(spss_file: BytesIO,xlsx_file: BytesIO):
    file_xlsx = get_temp_file(xlsx_file)
    varsList=pd.read_excel(file_xlsx,usecols="A,B",skiprows=3,names=["vars","varsTypes"]).dropna()
    colVarsList=pd.melt(pd.read_excel(file_xlsx,nrows=2),var_name="colVars",value_name="colVarsNames").drop(0)
    result=""
    colvars=colVarsList.iloc[:,0]

    for i in range(len(colvars)):
        var=colvars[i+1]
        if re.search("^[PFSV].*[1-90].*A",var):
            colvars[i+1]="$COL_"+re.search(".*A",var).group()[:-1]
        else:
            colvars[i+1]="COL_"+var

    for i in range(len(varsList)):
        result+=writeQuestion(varsList.iloc[i][0],varsList.iloc[i][1],colvars)
    return result

def getPenaltysCode(xlsx_file: BytesIO):
    try:
        file_xlsx = get_temp_file(xlsx_file)
        varsList=pd.read_excel(file_xlsx,usecols="A,B",skiprows=3,names=["vars","varsTypes"]).dropna()
        penaltyList=pd.read_excel(file_xlsx,usecols="E",skiprows=3,names=["penaltyVars"]).dropna()
        ref=penaltyList.iloc[0][0]
        penaltyList=penaltyList.drop(0)
        penaltyList=penaltyList.iloc[:,0]
        penaltyCode=""
        for i in range(len(varsList)):
            typevar=varsList.iloc[i][1]
            if typevar=="J":
                var1=varsList.iloc[i][0]
                var2=""
                for penal in penaltyList:
                    if re.search("_.*",var1).group()==re.search("_.*",penal).group():
                        var2=penal
                        break
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
        return "No Penaltys to calculated"

def getCruces(xlsx_file: BytesIO):
    try:
        file_xlsx = get_temp_file(xlsx_file)
        varsList=pd.read_excel(file_xlsx,usecols="A,B,F",skiprows=3,names=["vars","varsTypes","crossVars"]).dropna()
        crosscode=""
        for i in range(len(varsList)):
            crosscode+=writeQuestion(varsList.iloc[i][0],varsList.iloc[i][1],[varsList.iloc[i][2]])
        return crosscode
    except:
        return "No cruces"



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
                    agrupresult=writeAgrupMulti(agrupresult,prefix,multis,label2)
                    multis=[]
                    prefix=re.search(".*A",var).group()
                    multis.append(var)
        elif serie:
            agrupresult=writeAgrupMulti(agrupresult,prefix,multis,label2)
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
                        columnsclone=writeAgrupMulti(columnsclone,"COL_"+prefix,multis,label2)
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

def getCodeProcess(spss_file: BytesIO,colvars,varsTxt,qtypesTxt):
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
        print(var)
        qtype=qtypes[varsProcess.index(var)]
        result+=writeQuestion(var,colvars,qtype,result)
    return result

def writeAgrupMulti(txt,prefix,listVars,label):
    txt+= "\nMRSETS\n  /MCGROUP NAME=$"+prefix[:-1]+" LABEL='"+label +"'\n    VARIABLES="
    for var in listVars:
        txt+=var+" "
    txt+="\n  /DISPLAY NAME=[$"+prefix[:-1]+"].\n"
    return txt

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
                        columnsclone=writeAgrupMulti(columnsclone,"COL_"+prefix,multis,colVars.iloc[row][1])
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
                    agrupresult=writeAgrupMulti(agrupresult,prefix,multis,label2)
                    multis=[]
                    prefix=re.search(".*A",var).group()
                    multis.append(var)
        elif serie:
            agrupresult=writeAgrupMulti(agrupresult,prefix,multis,label2)
            multis=[]
            serie=False
        label2=label
    return agrupresult

def getSegmentCode(spss_file: BytesIO):
    try:
        temp_file_name = get_temp_file(spss_file)
        data, study_metadata = pyreadstat.read_sav(
            temp_file_name,
            apply_value_formats=False
        )

        refdict=study_metadata.variable_value_labels["REF.1"]
        filterdatabase=""
        namedatasetspss="ConjuntoDatos1"
        for refindex in data["REF.1"].unique():
            filterdatabase+="DATASET ACTIVATE "+ namedatasetspss+".\n"
            filterdatabase+="DATASET COPY REF_"+refdict[refindex]+".\nDATASET ACTIVATE REF_"+refdict[refindex]+".\nFILTER OFF.\nUSE ALL.\n"
            filterdatabase+="SELECT IF (REF.1 = "+str(int(refindex))+").\nEXECUTE.\n\n"
        return filterdatabase
    except:
        return "References variable not is REF.1"
def writeQuestion(varName,qtype, colVars):
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
        txt+="COUNT 'Total' F40.0, RESPONSES 'Total Respuestas' F40.0, COLPCT.RESPONSES.COUNT '%' F40.0]] BY TOTAL[C]"
    else:
        txt+="COUNT 'Total' F40.0, TOTALN 'Total Respuestas' F40.0, COLPCT.COUNT '%' F40.0]] BY TOTAL[C]"
    for colvar in colVars:
        txt+= " + "+colvar+" [C]"
    txt+="\n  /SLABELS POSITION=ROW\n  /CATEGORIES VARIABLES="+varName
    if qtype in ["E","J"]:
        txt+=" [&cat1, 5, 4, 3, 2, 1, &cat2] "
    elif qtype in ["M"]:
        txt+=" ORDER=D KEY=COUNT "
    else:
        txt+=" ORDER=A KEY=VALUE "

    if qtype in ["E","J"]:
        txt+="EMPTY=INCLUDE TOTAL=YES POSITION=AFTER"
    else:
        txt+="EMPTY=EXCLUDE TOTAL=YES POSITION=AFTER"

    txt+="\n  /CATEGORIES VARIABLES=TOTAL "
    for colvar in colVars:
        txt+= colvar+" "
    txt+="ORDER=A EMPTY=EXCLUDE"
    txt+=("\n  /CRITERIA CILEVEL=95\n  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN INCLUDEMRSETS=YES"
        + "\n  CATEGORIES=SUBTOTALS MERGE=YES STYLE=SIMPLE SHOWSIG=NO.\n")
    return txt
