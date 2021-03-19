from abc import ABC, abstractmethod
import pandas as pd


UNKNOWN_TOKENS = [
    "nan",
    "na",
    "nd"
    "n.d",
    "none",
    "-",
    "unknown",
    "n/a",
    "n/d",
    ""
]
UNKNOWN_REGEX = r"$^|n\.?[a|d|/|n]+\.?|^-$|unk.*|none"


def get_data_types():
    url = "https://raw.githubusercontent.com/Big-Life-Lab/covid-19-wastewater/main/site/Variables.csv"  # noqa
    variables = pd.read_csv(url)
    variables["variableName"] = variables["variableName"].str.lower()
    variables["variableType"] = variables["variableType"]\
        .replace(r"date(time)?", "datetime64[ns]", regex=True) \
        .replace("boolean", "bool") \
        .replace("float", "float64") \
        .replace("integer", "int64") \
        .replace("blob", "object")

    return variables\
        .groupby("tableName")[['variableName', 'variableType']] \
        .apply(lambda x: x.set_index('variableName').to_dict(orient='index')) \
        .to_dict()


DATA_TYPES = get_data_types()


def parse_types(table_name, series):
    variable_name = series.name.lower()
    types = DATA_TYPES
    lookup_table = types[table_name]
    lookup_type = lookup_table.get(variable_name, dict())
    desired_type = lookup_type.get("variableType", "string")
    if desired_type == "bool":
        series = series.astype(str)
        default_bool = "false" if "qualityFlag" in variable_name else "true"
        series = series.str.strip().str.lower()
        series = series.str.replace(
            UNKNOWN_REGEX, default_bool, regex=True)\
            .str.replace("oui", "true", case=False)\
            .str.replace("yes", "true", case=False)\
            .str.startswith("true")
    elif desired_type == "string" or desired_type == "category":
        series = series.astype(str)
        series = series.str.strip()
        series = series.str.replace(
            UNKNOWN_REGEX, "", regex=True, case=False)
        if variable_name != "wkt":
            series = series.str.lower()
    elif desired_type in ["inst64", "float64"]:
        series = pd.to_numeric(series, errors="coerce")

    series = series.astype(desired_type)
    return series


class BaseMapper(ABC):
    sample = None
    ww_measure = None
    site = None
    site_measure = None
    reporter = None
    lab = None
    assay_method = None
    instrument = None
    polygon = None
    cphd = None
    # Attribute name to source name
    conversion_dict = {
        "ww_measure": {
            "odm_name": "WWMeasure",
            "source_name": ""
            },
        "site_measure": {
            "odm_name": "SiteMeasure",
            "source_name": ""
            },
        "sample": {
            "odm_name": "Sample",
            "source_name": ""
            },
        "site": {
            "odm_name": "Site",
            "source_name": ""
            },
        "polygon": {
            "odm_name": "Polygon",
            "source_name": ""
            },
        "cphd": {
            "odm_name": "CovidPublicHealthData",
            "source_name": ""
            },
        "reporter": {
            "odm_name": "Reporter",
            "source_name": ""
            },
        "lab": {
            "odm_name": "Lab",
            "source_name": ""
            },
        "assay_method": {
            "odm_name": "AssayMethod",
            "source_name": ""
            },
        "instrument": {
            "odm_name": "Instrument",
            "source_name": ""
            },
    }

    @abstractmethod
    def read():
        pass

    @abstractmethod
    def validates(self):
        pass

    def type_cast_table(self, odm_name, df):
        return df.apply(
                lambda x: parse_types(odm_name, x),
                axis=0)