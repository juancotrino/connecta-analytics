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

def getCodeProcess(spss_file: BytesIO,colvars):
    result=""
    temp_file_name = get_temp_file(spss_file)
    data, study_metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )
    for var,scale in study_metadata.variable_value_labels.items():
        if re.search("ABIERTAS",var):
            break
        elif re.search("A_",var):
            continue
        elif len(scale)==5:
            result+="\n\nCTABLES\n  /VLABELS VARIABLES="+var+" "
            for colvar in colvars:
                result+=colvar +" "
            result+="DISPLAY=LABEL  /VLABELS VARIABLES=TOTAL DISPLAY=NONE\n  /PCOMPUTE &cat1 = EXPR([4]+[5])\n  /PPROPERTIES &cat1 LABEL = \"NETO TOP TWO BOX\" FORMAT=COLPCT.COUNT '1' F40.0 HIDESOURCECATS=NO\n  /PCOMPUTE &cat2 = EXPR([2]+[1])\n  /PPROPERTIES &cat2 LABEL = \"NETO BOTTOM TWO BOX\" FORMAT=COLPCT.COUNT '1' F40.0 HIDESOURCECATS=NO\n  /TABLE " + var +"[C][COUNT '1' F40.0, TOTALS[MEAN 'Promedio:' F40.2, STDDEV 'Desviación '+\n     'estándar:' F40.2, SEMEAN 'Error estándar:' F40.2, COUNT 'Total' F40.0, TOTALN 'Total Respuestas'\n     F40.0, COLPCT.COUNT '%' F40.0]] BY TOTAL[C]"
            for colvar in colvars:
                result+= " + "+colvar+" [C]"
            result+="\n  /SLABELS POSITION=ROW\n  /CATEGORIES VARIABLES="+var +" [&cat1, 5, 4, 3, 2, 1, &cat2] EMPTY=INCLUDE TOTAL=YES POSITION=AFTER"
            result+="\n  /CATEGORIES VARIABLES=TOTAL ORDER=A EMPTY=EXCLUDE TOTAL=YES POSITION=AFTER"
            for vari in colvars:
                if vari=="ESTRATOS":
                    result+= "\n  /CATEGORIES VARIABLES=ESTRATOS [6,7,10, 20, 30, 4, 5] EMPTY=INCLUDE"
                else:
                    result+="\n  /CATEGORIES VARIABLES="+vari +" ORDER=A KEY=VALUE EMPTY=EXCLUDE POSITION=AFTER"
            result+="\n  /CRITERIA CILEVEL=95\n  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN INCLUDEMRSETS=YES\n  CATEGORIES=SUBTOTALS MERGE=YES STYLE=SIMPLE SHOWSIG=NO."
        elif re.search("^[FP][1-90]",var):
            result+="\n\nCTABLES\n  /VLABELS VARIABLES="+var+" "
            for colvar in colvars:
                result+=colvar +" "
            result+="DISPLAY=LABEL  /VLABELS VARIABLES=TOTAL DISPLAY=NONE\n  /PCOMPUTE &cat1 = EXPR([4]+[5])\n  /PPROPERTIES &cat1 LABEL = \"NETO TOP TWO BOX\" FORMAT=COLPCT.COUNT '1' F40.0 HIDESOURCECATS=NO\n  /PCOMPUTE &cat2 = EXPR([2]+[1])\n  /PPROPERTIES &cat2 LABEL = \"NETO BOTTOM TWO BOX\" FORMAT=COLPCT.COUNT '1' F40.0 HIDESOURCECATS=NO\n  /TABLE " + var +"[C][COUNT '1' F40.0, TOTALS[MEAN 'Promedio:' F40.2, STDDEV 'Desviación '+\n     'estándar:' F40.2, SEMEAN 'Error estándar:' F40.2, COUNT 'Total' F40.0, TOTALN 'Total Respuestas'\n     F40.0, COLPCT.COUNT '%' F40.0]] BY TOTAL[C]"
            for colvar in colvars:
                result+= " + "+colvar+" [C]"
            result+="\n  /SLABELS POSITION=ROW\n  /CATEGORIES VARIABLES="+var +" ORDER=A KEY=VALUE EMPTY=INCLUDE TOTAL=YES POSITION=AFTER"
            result+="\n  /CATEGORIES VARIABLES=TOTAL ORDER=A EMPTY=EXCLUDE TOTAL=YES POSITION=AFTER"
            for vari in colvars:
                if vari=="ESTRATOS":
                    result+= "\n  /CATEGORIES VARIABLES=ESTRATOS [6,7,1, 2, 3, 4, 5] EMPTY=INCLUDE"
                else:
                    result+="\n  /CATEGORIES VARIABLES="+vari +" ORDER=A KEY=VALUE EMPTY=EXCLUDE POSITION=AFTER"
            result+="\n  /CRITERIA CILEVEL=95\n  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN INCLUDEMRSETS=YES\n  CATEGORIES=SUBTOTALS MERGE=YES STYLE=SIMPLE SHOWSIG=NO."

    return result
