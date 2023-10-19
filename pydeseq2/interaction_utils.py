import copy
from itertools import product
from functools import reduce
from pandas.api.types import is_numeric_dtype
def merge_categorical_columns_inplace(metadata, left_factor, right_factor):
    """
    Merge two categorical columns in a pandas dataframe into a new column.
    
    Note that it doesn't create every possible combinaison of the two columns
    only those that are present in the dataframe to avoid empty groups.

    Parameters
    ----------
    metadata : pandas.DataFrame
        The dataframe to modify.
    left_factor : str
        The name of the first column to merge.
    right_factor : str
        The name of the second column to merge.

    Returns
    -------
    None
        Modifies the dataframe in place.
    """
    interaction_column_name = left_factor + ":" + right_factor
    metadata[interaction_column_name] = metadata[left_factor].astype(str) + metadata[right_factor].astype(str)


def merge_two_columns(left_factor, right_factor, metadata, continuous_factors):
    """Merge two columns in the general case.

    Handles all cases with both columns categorical, both numeric or one numeric
    and the other categorical.

    Parameters
    ----------
    left_factor : str
        The name of the first column to merge.
    right_factor : str
        The name of the second column to merge.
    metadata : pd.DataFrame
        The design matrix.
    continuous_factors : list
        The list of known continuous factors.

    Returns
    -------
    None
        modifies metadata inplace.
    """
    interaction_column_name = left_factor + ":" + right_factor
    is_left_categorical = left_factor not in continuous_factors
    is_right_categorical = right_factor not in continuous_factors
    is_any_categorical = is_left_categorical or is_right_categorical
    if not is_any_categorical:
        # All factors are continuous
        metadata[interaction_column_name] = metadata[left_factor] * metadata[right_factor]
        continuous_factors.append(interaction_column_name)
        return [interaction_column_name]
    else:
        if is_left_categorical and is_right_categorical:
            merge_categorical_columns_inplace(metadata, left_factor, right_factor)
            return [interaction_column_name]

        elif is_left_categorical:
            cat_col_name = left_factor
            cont_col_name = right_factor
        elif is_right_categorical:
            cat_col_name = right_factor
            cont_col_name = left_factor

        multiplex_continuous_factor(metadata, cat_col_name, cont_col_name, is_right_categorical, continuous_factors)
        


def multiplex_continuous_factor(metadata, cat_col_name, cont_col_name, is_right_categorical, continuous_factors):
    """Multiplex continuous factor into categorical levels.

    Merge two columns in the hybrid case where one is categorical and the other continuous.

    Parameters
    ----------
    metadata : pd.DataFrame
        The design matrix.
    cat_col_name : str
        The name of the categorical column either left or right.
    cont_col_name : _type_
        The name of the continuous column either left or right.
    is_right_categorical : bool
        Whether or not the categorical was on the right or left. Needed
        for the creation of the new name.
    continuous_factors : list
        The list of all known continuous factors.

    Returns
    -------
    list
        All columns that are interacting.
    """
    cat_levels = metadata[cat_col_name].unique()
    # We multiplex the continuous variable to cat_levels continuous variables
    # that are cont_col_name when the level is activated and 0 otherwise
    interaction_column_names = []
    left_factor = cont_col_name if is_right_categorical else cat_col_name
    right_factor = cat_col_name if is_right_categorical else cont_col_name
    for cat_level in cat_levels:
        if is_right_categorical:
            right_col_name = right_factor + f"_{cat_level}"
            left_col_name = left_factor
        else:
            left_col_name = left_factor+ f"_{cat_level}"
            right_col_name = right_factor
        current_col_name = left_col_name + ":" + right_col_name

        # Following lines exist only because we don't want to create all zero columns
        cat_factors_involved = [factor for factor in current_col_name.split(":") if "_" in factor]
        cat_factors_involved_names = [factor.split("_")[0] for factor in cat_factors_involved]
        cat_factors_involved_levels = [factor.split("_")[1] for factor in cat_factors_involved]
        metadata_cat_involved = [metadata[cat_factor_name].astype("str") for cat_factor_name in cat_factors_involved_names]
        # if metadata_cat_involved has only one element then no need to check if the combinaison is in the dataframe
        if len(metadata_cat_involved) > 1:
            # For some reasons sum doesn't work
            existing_categories = list(set(reduce(lambda a, b: a+b, metadata_cat_involved).tolist()))
            combinaison_to_be_created = reduce(lambda a, b: a+b, cat_factors_involved_levels)
            if combinaison_to_be_created not in existing_categories:
                continue

        metadata[current_col_name] = (metadata[cat_col_name] == cat_level).astype("float") * metadata[cont_col_name]
        interaction_column_names.append(current_col_name)
        continuous_factors.append(current_col_name)
    return interaction_column_names

def build_single_interaction_factor(metadata, design_factor, continuous_factors):
    """Build interaction column into the design matrix.

    Parameters
    ----------
    metadata : pd.DataFrame
        The design matrix.
    design_factor : str
        The name of the column with potentially interaction terms.
    continuous_factors : list
        All factors known to be continuous.
    """
    interacting_columns = merge_columns(metadata, design_factor, continuous_factors)
    # Remove all intermediate columns
    # Note this could be removed in case one wants to also know inner interacting terms
    columns_to_drop = [col for col in metadata.columns if not(col in interacting_columns) and any([not(int_col in col) for int_col in interacting_columns])]
    metadata.drop(columns=columns_to_drop, inplace=True)


def merge_columns(metadata, design_factor, continuous_factors):
    """Merge any combination of any number of columns interacting.

    Parameters
    ----------
    metadata : pd.DataFrame
        The design matrix.
    design_factor : str
        The column either containing interaction terms or not.
    continuous_factors : list
        All known coontinuous factors.

    Returns
    -------
    list
        All original coolumns interacting.

    Raises
    ------
    ValueError
        If the columns to interact do not exist.
    """
    if ":" in design_factor:
        design_factor = design_factor.split(':')
        if not all([des_f in metadata.columns for des_f in design_factor]):
            raise ValueError(f"Some of the design factors in {design_factor} are not in metadata. It is not allowed to use : in the column names as it is interpreted as an interaction.")
        # The tuples are useful to know which columns are original and which are created
        
    else:
        # We leave the dataframe metadata unchanged
        return [design_factor]
    # List is at least of size 2
    merge_two_columns(design_factor[0], design_factor[1], metadata, continuous_factors)
    for j in range(2, len(design_factor)):
        # Only some columns of metadata are eligible to be merged
        metadata_cols_to_be_merged = [col for col in metadata.columns if any([des_f_temp in col for des_f_temp in design_factor])]
        for col in metadata_cols_to_be_merged:
            merge_two_columns(col, design_factor[j], metadata, continuous_factors)
    return design_factor

import pandas as pd 
df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6], 'c': ["7", "8", "9"]})
build_single_interaction_factor(df, "a:b:c", continuous_factors=["a","b"])


print(df)