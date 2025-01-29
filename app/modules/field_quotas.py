import itertools

import numpy as np
import pandas as pd


def check_percentage_total(
    variables: dict[str, pd.DataFrame], variable_type: str = "independent"
):
    for variable, data in variables.items():
        match variable_type:
            case "independent":
                if data["percentage"].sum() != 100:
                    raise Exception(
                        f"Percentage sum for variable '{variable}' is not 100. "
                        f"Actual sum: {data['percentage'].sum()}."
                    )
            case "nested":
                higher_variable = variable.split("-")[0].strip()
                grouped_data = data.groupby(higher_variable).sum().reset_index()
                unique_values = data.iloc[:, 0].unique()

                for value in unique_values:
                    value_percentage_sum = grouped_data[
                        grouped_data[higher_variable] == value
                    ]["percentage"].to_list()[0]
                    if value_percentage_sum != 100:
                        raise Exception(
                            f"Percentage sum for nested variable '{variable}' "
                            f"for value '{value}' is not 100. "
                            f"Actual sum: {value_percentage_sum}."
                        )


def get_expanded_surveys(
    total_surveys: int,
    total_pollsters: int,
    variable_percentages_dict: dict,
    variable_nested_percentages_dict: dict,
    selected_variables_data: dict,
    selected_variables: list[str],
):
    if not total_surveys:
        raise Exception("Missing total number of surveys.")

    if not total_pollsters:
        raise Exception("Missing number of pollsters.")

    ordered_selected_variables_data = {
        variable: selected_variables_data[variable] for variable in selected_variables
    }

    combinations = list(itertools.product(*ordered_selected_variables_data.values()))

    combinations_df = pd.DataFrame(
        combinations, columns=ordered_selected_variables_data.keys()
    )

    for variable in variable_percentages_dict:
        combinations_df = pd.merge(
            combinations_df,
            variable_percentages_dict[variable],
            on=variable,
            how="left",
            suffixes=[f"_comb_{variable}", f"_{variable}"],
        )

    for variable in variable_nested_percentages_dict:
        combinations_df = pd.merge(
            combinations_df,
            variable_nested_percentages_dict[variable],
            on=[v.strip() for v in variable.split("-")],
            how="left",
            suffixes=[f"_independent_{variable}", f"_{variable}"],
        )
    percentage_columns = combinations_df.loc[
        :, combinations_df.columns.str.contains("percentage")
    ]
    combinations_df[percentage_columns.columns] = percentage_columns.astype(float)
    combinations_df.loc[:, combinations_df.columns.str.contains("percentage")] /= 100
    percentage_columns = combinations_df.loc[
        :, combinations_df.columns.str.contains("percentage")
    ]
    combinations_df["percentage"] = percentage_columns.prod(axis=1)
    combinations_df["surveys_float"] = combinations_df["percentage"] * total_surveys
    combinations_df["surveys"] = round(combinations_df["surveys_float"])

    # Calculate the difference between the total surveys and the sum of rounded surveys
    survey_diff = int(total_surveys - combinations_df["surveys"].sum())

    # Adjust the survey counts to match total_surveys
    if survey_diff != 0:
        # Find the rows with the smallest fractional part
        differences = (
            combinations_df["surveys_float"] - combinations_df["surveys"]
        ).abs()

        # Sort the rows based on the differences (to adjust the smallest fractional part)
        combinations_df["adjustment"] = differences
        combinations_df.sort_values("adjustment", ascending=False, inplace=True)

        # Adjust the rows to make the total sum match total_surveys
        for i in range(abs(survey_diff)):
            if survey_diff > 0:
                # Increment the survey count for the row with the smallest fractional part
                combinations_df.iloc[i, combinations_df.columns.get_loc("surveys")] += 1
            elif survey_diff < 0:
                # Decrement the survey count for the row with the smallest fractional part, but ensure it's not negative
                if (
                    combinations_df.iloc[i, combinations_df.columns.get_loc("surveys")]
                    > 0
                ):
                    combinations_df.iloc[
                        i, combinations_df.columns.get_loc("surveys")
                    ] -= 1

    # Ensure surveys are integers and non-negative
    combinations_df["surveys"] = combinations_df["surveys"].clip(lower=0).astype(int)

    # Ensure surveys are integers
    combinations_df["surveys"] = combinations_df["surveys"].astype(int)

    # Create the new DataFrame by repeating each row based on the 'surveys' column
    expanded_df = combinations_df[selected_variables].loc[
        np.repeat(combinations_df.index.values, combinations_df["surveys"])
    ]

    # Optionally, reset the index for the new DataFrame
    expanded_df = expanded_df.sort_values(selected_variables).reset_index(drop=True)

    # Create an array of 16 elements (you can change these values as needed)
    pollsters = np.arange(1, total_pollsters + 1)  # Here I'm using numbers 1 to 16

    # Repeat the elements array until it covers the entire number of rows
    repeated_elements = np.tile(
        pollsters, int(np.ceil(len(expanded_df) / total_pollsters))
    )[: len(expanded_df)]

    # Add this array as a new column in your DataFrame
    expanded_df["Pollster"] = repeated_elements

    # Ensure final length matches total_surveys
    if len(expanded_df) != total_surveys:
        # If there's a discrepancy, adjust the number of rows
        expanded_df = expanded_df.head(total_surveys)

    return expanded_df
