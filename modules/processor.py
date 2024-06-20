from io import BytesIO
import re
import pandas as pd
from modules.segment_spss import get_temp_file
import pyreadstat

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

def getCodeProcess(spss_file: BytesIO,colvars,varsTxt,qtypesTxt):
    result=""
    agrupresult=""
    varsProcess=[var for var in varsTxt.splitlines()]
    qtypes=[qtype for qtype in qtypesTxt.splitlines()]

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
        if re.search("A_",var):
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

    for var in varsProcess:
        qtype=qtypes[varsProcess.index(var)]
        result=writeQuestion(var,colvars,qtype,result)
    return agrupresult,result

def writeAgrupMulti(txt,prefix,listVars,label):
    txt+= "\nMRSETS\n  /MCGROUP NAME=$"+prefix[:-1]+" LABEL='"+label +"'\n    VARIABLES="
    for var in listVars:
        txt+=var+" "
    txt+="\n  /DISPLAY NAME=[$"+prefix[:-1]+"]."
    return txt

# def writeQuestion(varName, colVars,qtype,txt):
#     match qtype:
#             case "M":
#                 print(varName)
#                 multiquestionName="$"+re.search(".*A",varName).group()[:-1]
#                 txt+="\nCTABLES\n  /VLABELS VARIABLES="+ multiquestionName+" "
#                 for colvar in colVars:
#                     txt+= colvar+" "
#                 txt+="DISPLAY=LABEL  /VLABELS VARIABLES=TOTAL DISPLAY=NONE\n  /TABLE "+multiquestionName+" [C][COLPCT.COUNT '1' F40.0, TOTALS[COUNT 'Total' F40.0, RESPONSES 'Total Respuestas' F40.0, COLPCT.RESPONSES.COUNT '%' F40.0]] BY TOTAL[C]"
#                 for colvar in colVars:
#                     txt+= " + "+colvar+" [C]"
#                 txt+="\n  /SLABELS POSITION=ROW\n  /CATEGORIES VARIABLES=" +multiquestionName+ " ORDER=D KEY=COLPCT.COUNT ("+multiquestionName+") EMPTY=EXCLUDE TOTAL=YES POSITION=AFTER\n  /CATEGORIES VARIABLES=TOTAL ORDER=A KEY=VALUE EMPTY=INCLUDE POSITION=AFTER"
#                 for colvar in colVars:
#                     txt+="\n  /CATEGORIES VARIABLES="+colvar +" ORDER=A KEY=VALUE EMPTY=EXCLUDE POSITION=AFTER"
#                 txt+="\n  /CRITERIA CILEVEL=95\n  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN INCLUDEMRSETS=YES\n    CATEGORIES=SUBTOTALS MERGE=YES STYLE=SIMPLE SHOWSIG=NO."
#             case "E":
#                 txt+="\n\nCTABLES\n  /VLABELS VARIABLES="+varName+" TOTAL "
#                 for colvar in colVars:
#                     txt+=colvar +" "
#                 txt+=("DISPLAY=LABEL  \n  /PCOMPUTE &cat1 = EXPR([4]+[5])"
#                       + "\n  /PPROPERTIES &cat1 LABEL = \"NETO TOP TWO BOX\" FORMAT=COLPCT.COUNT '1' F40.0 HIDESOURCECATS=NO"
#                       + "\n  /PCOMPUTE &cat2 = EXPR([2]+[1])\n  /PPROPERTIES &cat2 LABEL = \"NETO BOTTOM TWO BOX\" FORMAT=COLPCT.COUNT '1' F40.0 HIDESOURCECATS=NO"
#                       + "\n  /TABLE " + varName +"[C][COLPCT.COUNT '1' F40.0, TOTALS[MEAN 'Promedio:' F40.2, STDDEV 'Desviación '+"
#                       + "\n     'estándar:' F40.2, SEMEAN 'Error estándar:' F40.2, COUNT 'Total' F40.0, TOTALN 'Total Respuestas'"
#                       + "\n     F40.0, COLPCT.COUNT '%' F40.0]] BY TOTAL[C]")
#                 for colvar in colVars:
#                     txt+= " + "+colvar+" [C]"
#                 txt+="\n  /SLABELS POSITION=ROW\n  /CATEGORIES VARIABLES="+varName +" [&cat1, 5, 4, 3, 2, 1, &cat2] EMPTY=INCLUDE TOTAL=YES POSITION=AFTER"
#                 txt+="\n  /CATEGORIES VARIABLES=TOTAL ORDER=A EMPTY=EXCLUDE TOTAL=NO POSITION=AFTER"
#                 for colvar in colVars:
#                     txt+="\n  /CATEGORIES VARIABLES="+colvar +" ORDER=A KEY=VALUE EMPTY=EXCLUDE POSITION=AFTER"
#                 txt+="\n  /CRITERIA CILEVEL=95\n  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN INCLUDEMRSETS=YES\n  CATEGORIES=SUBTOTALS MERGE=YES STYLE=SIMPLE SHOWSIG=NO."
#             case "A":
#                 txt+="\n\nCTABLES\n  /VLABELS VARIABLES="+varName+" TOTAL "
#                 for colvar in colVars:
#                     txt+=colvar +" "
#                 txt+=("DISPLAY=LABEL  "
#                       + "\n  /TABLE " + varName +" [C][COLPCT.COUNT '1' F40.0, TOTALS[MEAN 'Promedio:' F40.2, STDDEV 'Desviación '+"
#                       + "\n     'estándar:' F40.2, SEMEAN 'Error estándar:' F40.2, COUNT 'Total' F40.0, TOTALN 'Total Respuestas'"
#                       + "\n     F40.0, COLPCT.COUNT '%' F40.0]] BY TOTAL[C]")
#                 for colvar in colVars:
#                     txt+= " + "+colvar+" [C]"
#                 txt+="\n  /SLABELS POSITION=ROW\n  /CATEGORIES VARIABLES="+varName +" ORDER=A EMPTY=EXCLUDE TOTAL=YES POSITION=AFTER"
#                 txt+="\n  /CATEGORIES VARIABLES=TOTAL ORDER=A EMPTY=EXCLUDE TOTAL=NO POSITION=AFTER"
#                 for colvar in colVars:
#                     txt+="\n  /CATEGORIES VARIABLES="+colvar +" ORDER=A KEY=VALUE EMPTY=EXCLUDE POSITION=AFTER"
#                 txt+="\n  /CRITERIA CILEVEL=95\n  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN INCLUDEMRSETS=YES\n  CATEGORIES=SUBTOTALS MERGE=YES STYLE=SIMPLE SHOWSIG=NO."
#             case "N":
#                 txt+="\n\nCTABLES\n  /VLABELS VARIABLES="+varName+" TOTAL "
#                 for colvar in colVars:
#                     txt+=colvar +" "
#                 txt+=("DISPLAY=LABEL  "
#                       + "\n  /TABLE " + varName +" [C][COLPCT.COUNT '1' F40.0, TOTALS[COUNT F40.0, TOTALN F40.0, COLPCT.TOTALN '%' F40.0]] BY TOTAL[C]")
#                 for colvar in colVars:
#                     txt+= " + "+colvar+" [C]"
#                 txt+="\n  /SLABELS POSITION=ROW\n  /CATEGORIES VARIABLES="+varName +" ORDER=A EMPTY=INCLUDE TOTAL=YES POSITION=AFTER"
#                 txt+="\n  /CATEGORIES VARIABLES=TOTAL ORDER=A EMPTY=EXCLUDE TOTAL=NO POSITION=AFTER"
#                 for colvar in colVars:
#                     txt+="\n  /CATEGORIES VARIABLES="+colvar +" ORDER=A KEY=VALUE EMPTY=EXCLUDE POSITION=AFTER"
#                 txt+="\n  /CRITERIA CILEVEL=95\n  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN INCLUDEMRSETS=YES\n  CATEGORIES=SUBTOTALS MERGE=YES STYLE=SIMPLE SHOWSIG=NO."
#             case "J":
#                 txt+="\n\nCTABLES\n  /VLABELS VARIABLES="+varName+" TOTAL "
#                 for colvar in colVars:
#                     txt+=colvar +" "
#                 txt+=("DISPLAY=LABEL \n  /PCOMPUTE &cat1 = EXPR([4]+[5])"
#                       + "\n  /PPROPERTIES &cat1 LABEL = \"NETO TOP TWO BOX\" FORMAT=COLPCT.COUNT '1' F40.0 HIDESOURCECATS=NO"
#                       + "\n  /PCOMPUTE &cat2 = EXPR([2]+[1])\n  /PPROPERTIES &cat2 LABEL = \"NETO BOTTOM TWO BOX\" FORMAT=COLPCT.COUNT '1' F40.0 HIDESOURCECATS=NO"
#                       + "\n  /TABLE " + varName +" [C][COLPCT.COUNT '1' F40.0, TOTALS[COUNT F40.0, TOTALN F40.0, COLPCT.TOTALN '%' F40.0]] BY TOTAL[C]")
#                 for colvar in colVars:
#                     txt+= " + "+colvar+" [C]"
#                 txt+="\n  /SLABELS POSITION=ROW\n  /CATEGORIES VARIABLES="+varName +" [&cat1, 5, 4, 3, 2, 1, &cat2] EMPTY=INCLUDE TOTAL=YES POSITION=AFTER"
#                 txt+="\n  /CATEGORIES VARIABLES=TOTAL ORDER=A EMPTY=EXCLUDE TOTAL=NO POSITION=AFTER"
#                 for colvar in colVars:
#                     txt+="\n  /CATEGORIES VARIABLES="+colvar +" ORDER=A KEY=VALUE EMPTY=EXCLUDE POSITION=AFTER"
#                 txt+="\n  /CRITERIA CILEVEL=95\n  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN INCLUDEMRSETS=YES\n  CATEGORIES=SUBTOTALS MERGE=YES STYLE=SIMPLE SHOWSIG=NO."

#     return txt

def writeQuestion(varName, colVars,qtype,txt):
    match qtype:
            case "M":
                multiquestionName="$"+re.search(".*A",varName).group()[:-1]
                txt+="\nCTABLES\n  /VLABELS VARIABLES="+ multiquestionName+" "
                for colvar in colVars:
                    txt+= colvar+" "
                txt+="DISPLAY=LABEL  /VLABELS VARIABLES=TOTAL DISPLAY=NONE\n  /TABLE "+multiquestionName+" [C][COUNT '1' F40.0, TOTALS[COUNT 'Total' F40.0, RESPONSES 'Total Respuestas' F40.0, COLPCT.RESPONSES.COUNT '%' F40.0]] BY TOTAL[C]"
                for colvar in colVars:
                    txt+= " + "+colvar+" [C]"
                txt+="\n  /SLABELS POSITION=ROW\n  /CATEGORIES VARIABLES=" +multiquestionName+ " ORDER=D KEY=COUNT ("+multiquestionName+") EMPTY=EXCLUDE TOTAL=YES POSITION=AFTER\n  /CATEGORIES VARIABLES=TOTAL ORDER=A KEY=VALUE EMPTY=INCLUDE POSITION=AFTER"
                for colvar in colVars:
                    txt+="\n  /CATEGORIES VARIABLES="+colvar +" ORDER=A KEY=VALUE EMPTY=EXCLUDE POSITION=AFTER"
                txt+="\n  /CRITERIA CILEVEL=95\n  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN INCLUDEMRSETS=YES\n    CATEGORIES=SUBTOTALS MERGE=YES STYLE=SIMPLE SHOWSIG=NO."
            case "E":
                txt+="\n\nCTABLES\n  /VLABELS VARIABLES="+varName+" TOTAL "
                for colvar in colVars:
                    txt+=colvar +" "
                txt+=("DISPLAY=LABEL  \n  /PCOMPUTE &cat1 = EXPR([4]+[5])"
                      + "\n  /PPROPERTIES &cat1 LABEL = \"NETO TOP TWO BOX\" FORMAT=COUNT '1' F40.0 HIDESOURCECATS=NO"
                      + "\n  /PCOMPUTE &cat2 = EXPR([2]+[1])\n  /PPROPERTIES &cat2 LABEL = \"NETO BOTTOM TWO BOX\" FORMAT=COUNT '1' F40.0 HIDESOURCECATS=NO"
                      + "\n  /TABLE " + varName +"[C][COUNT '1' F40.0, TOTALS[MEAN 'Promedio:' F40.2, STDDEV 'Desviación '+"
                      + "\n     'estándar:' F40.2, SEMEAN 'Error estándar:' F40.2, COUNT 'Total' F40.0, TOTALN 'Total Respuestas'"
                      + "\n     F40.0, COLPCT.COUNT '%' F40.0]] BY TOTAL[C]")
                for colvar in colVars:
                    txt+= " + "+colvar+" [C]"
                txt+="\n  /SLABELS POSITION=ROW\n  /CATEGORIES VARIABLES="+varName +" [&cat1, 5, 4, 3, 2, 1, &cat2] EMPTY=INCLUDE TOTAL=YES POSITION=AFTER"
                txt+="\n  /CATEGORIES VARIABLES=TOTAL ORDER=A EMPTY=EXCLUDE TOTAL=NO POSITION=AFTER"
                for colvar in colVars:
                    txt+="\n  /CATEGORIES VARIABLES="+colvar +" ORDER=A KEY=VALUE EMPTY=EXCLUDE POSITION=AFTER"
                txt+="\n  /CRITERIA CILEVEL=95\n  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN INCLUDEMRSETS=YES\n  CATEGORIES=SUBTOTALS MERGE=YES STYLE=SIMPLE SHOWSIG=NO."
            case "A":
                txt+="\n\nCTABLES\n  /VLABELS VARIABLES="+varName+" TOTAL "
                for colvar in colVars:
                    txt+=colvar +" "
                txt+=("DISPLAY=LABEL  "
                      + "\n  /TABLE " + varName +" [C][COUNT '1' F40.0, TOTALS[MEAN 'Promedio:' F40.2, STDDEV 'Desviación '+"
                      + "\n     'estándar:' F40.2, SEMEAN 'Error estándar:' F40.2, COUNT 'Total' F40.0, TOTALN 'Total Respuestas'"
                      + "\n     F40.0, COLPCT.COUNT '%' F40.0]] BY TOTAL[C]")
                for colvar in colVars:
                    txt+= " + "+colvar+" [C]"
                txt+="\n  /SLABELS POSITION=ROW\n  /CATEGORIES VARIABLES="+varName +" ORDER=A EMPTY=EXCLUDE TOTAL=YES POSITION=AFTER"
                txt+="\n  /CATEGORIES VARIABLES=TOTAL ORDER=A EMPTY=EXCLUDE TOTAL=NO POSITION=AFTER"
                for colvar in colVars:
                    txt+="\n  /CATEGORIES VARIABLES="+colvar +" ORDER=A KEY=VALUE EMPTY=EXCLUDE POSITION=AFTER"
                txt+="\n  /CRITERIA CILEVEL=95\n  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN INCLUDEMRSETS=YES\n  CATEGORIES=SUBTOTALS MERGE=YES STYLE=SIMPLE SHOWSIG=NO."
            case "N":
                txt+="\n\nCTABLES\n  /VLABELS VARIABLES="+varName+" TOTAL "
                for colvar in colVars:
                    txt+=colvar +" "
                txt+=("DISPLAY=LABEL  "
                      + "\n  /TABLE " + varName +" [C][COUNT '1' F40.0, TOTALS[COUNT F40.0, TOTALN F40.0, COLPCT.TOTALN '%' F40.0]] BY TOTAL[C]")
                for colvar in colVars:
                    txt+= " + "+colvar+" [C]"
                txt+="\n  /SLABELS POSITION=ROW\n  /CATEGORIES VARIABLES="+varName +" ORDER=A EMPTY=INCLUDE TOTAL=YES POSITION=AFTER"
                txt+="\n  /CATEGORIES VARIABLES=TOTAL ORDER=A EMPTY=EXCLUDE TOTAL=NO POSITION=AFTER"
                for colvar in colVars:
                    txt+="\n  /CATEGORIES VARIABLES="+colvar +" ORDER=A KEY=VALUE EMPTY=EXCLUDE POSITION=AFTER"
                txt+="\n  /CRITERIA CILEVEL=95\n  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN INCLUDEMRSETS=YES\n  CATEGORIES=SUBTOTALS MERGE=YES STYLE=SIMPLE SHOWSIG=NO."
            case "J":
                txt+="\n\nCTABLES\n  /VLABELS VARIABLES="+varName+" TOTAL "
                for colvar in colVars:
                    txt+=colvar +" "
                txt+=("DISPLAY=LABEL \n  /PCOMPUTE &cat1 = EXPR([4]+[5])"
                      + "\n  /PPROPERTIES &cat1 LABEL = \"NETO TOP TWO BOX\" FORMAT=COUNT '1' F40.0 HIDESOURCECATS=NO"
                      + "\n  /PCOMPUTE &cat2 = EXPR([2]+[1])\n  /PPROPERTIES &cat2 LABEL = \"NETO BOTTOM TWO BOX\" FORMAT=COUNT '1' F40.0 HIDESOURCECATS=NO"
                      + "\n  /TABLE " + varName +" [C][COUNT '1' F40.0, TOTALS[COUNT F40.0, TOTALN F40.0, COLPCT.TOTALN '%' F40.0]] BY TOTAL[C]")
                for colvar in colVars:
                    txt+= " + "+colvar+" [C]"
                txt+="\n  /SLABELS POSITION=ROW\n  /CATEGORIES VARIABLES="+varName +" [&cat1, 5, 4, 3, 2, 1, &cat2] EMPTY=INCLUDE TOTAL=YES POSITION=AFTER"
                txt+="\n  /CATEGORIES VARIABLES=TOTAL ORDER=A EMPTY=EXCLUDE TOTAL=NO POSITION=AFTER"
                for colvar in colVars:
                    txt+="\n  /CATEGORIES VARIABLES="+colvar +" ORDER=A KEY=VALUE EMPTY=EXCLUDE POSITION=AFTER"
                txt+="\n  /CRITERIA CILEVEL=95\n  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN INCLUDEMRSETS=YES\n  CATEGORIES=SUBTOTALS MERGE=YES STYLE=SIMPLE SHOWSIG=NO."

    return txt
