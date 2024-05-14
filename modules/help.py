help_segment_spss = """
Create a scenario by filling up the columns in the table below.

- Scenario Name: Choose a descriptive name for the scenario. This field will also be used in the output `.sav` database.
- Variables: Write the variables to keep from the original `.sav` database separated by a comma `,`. E.g. `P1.1,P3,P34_2.1`.
You can also copy-paste the variables from the `.sav` database. Leave it empty if you want to keep all variables from the `.sav`.
- Condition: Write the conditions that are going to be used in the filtering of the registries. This conditions must have a query syntaxis as shown below:
    - For a single condition:
        - ``` `P1.1` > 30 ```
        - ``` `P32_1` <= 15 ```
        - ``` `P23` == 2 ```
    - For multiple conditions:
        - ``` `N02` <= 4 & `N23` in [1, 2, 4] ```
        - ``` `P3` == 4 | (`P3` == 3 & `P4` == 'Si') ```

    _Hint: Note that the symbols `&` and `|` mean `and` and `or` clauses respectively._
- Cross Variable (Chi2): If you want to generate a Chi2 report, write in this field the Cross Variable. If no Chi2 is needed, leave it empty.

"""
