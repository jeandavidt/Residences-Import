import json
import os
import sqlite3
import warnings

import numpy as np
import pandas as pd
import requests
from sqlalchemy import create_engine

import utilities
import visualization_helpers

# Set pandas to raise en exception when using chained assignment,
# as that may lead to values being set on a view of the data
# instead of on the data itself.
pd.options.mode.chained_assignment = 'raise'


class Odm:
    """Data class that holds the contents of the
    tables defined in the Ottawa Data Model (ODM).
    The tables are stored as pandas DataFrames. Utility
    functions are provided to manipulate the data for further analysis.
    """
    def __init__(
        self,
        sample: pd.DataFrame = None,
        ww_measure: pd.DataFrame = None,
        site: pd.DataFrame = None,
        site_measure: pd.DataFrame = None,
        reporter: pd.DataFrame = None,
        lab: pd.DataFrame = None,
        assay_method: pd.DataFrame = None,
        instrument: pd.DataFrame = None,
        polygon: pd.DataFrame = None,
        cphd: pd.DataFrame = None,
        lookup: pd.DataFrame = None
            ) -> None:

        self.sample = sample
        self.ww_measure = ww_measure
        self.site = site
        self.site_measure = site_measure
        self.reporter = reporter
        self.lab = lab
        self.assay_method = assay_method
        self.instrument = instrument
        self.polygon = polygon
        self.cphd = cphd

    conversion_dict = {
        "ww_measure": {
            "odm_name": "WWMeasure",
            "excel_name": "WWMeasure",
        },
        "site_measure": {
            "odm_name": "SiteMeasure",
            "excel_name": "SiteMeasure",
        },
        "sample": {
            "odm_name": "Sample",
            "excel_name": "Sample",
        },
        "site": {
            "odm_name": "Site",
            "excel_name": "Site",
        },
        "polygon": {
            "odm_name": "Polygon",
            "excel_name": "Polygon",
        },
        "cphd": {
            "odm_name": "CovidPublicHealthData",
            "excel_name": "CPHD",
        },
        "reporter": {
            "odm_name": "Reporter",
            "excel_name": "Reporter"
        },
        "lab": {
            "odm_name": "Lab",
            "excel_name": "Lab"
        },
        "assay_method": {
            "odm_name": "AssayMethod",
            "excel_name": "AssayMethod"
        },
        "instrument": {
            "odm_name": "Instrument",
            "excel_name": "Instrument"
        },
    }

    def __default_value_by_dtype(
        self, dtype: str
            ):
        """gets you a default value of the correct data type to create new
        columns in a pandas DataFrame

        Parameters
        ----------
        dtype : str
            string name of the data type (found with df[column].dtype)

        Returns
        -------
        [pd.NaT, np.nan, str, None]
            The corresponding default value
        """
        null_values = {
            "datetime64[ns]": pd.NaT,
            "float64": np.nan,
            "int64": np.nan,
            "object": ""
        }
        return null_values.get(dtype, np.nan)

    def __widen(
        self,
        df: pd.DataFrame,
        features: list[str],
        qualifiers: list[str]
            ) -> pd.DataFrame:
        """Takes important characteristics inside a table (features) and
        creates new columns to store them based on the value of other columns
        (qualifiers).

        Parameters
        ----------
        df : pd.DataFrame
            The DataFrame we are operating on.
        features : list[str]
            List of column names that contain the features to extract.
        qualifiers : list[str]
            List of column names that contain the qualifying information.

        Returns
        -------
        pd.DataFrame
            DataFrame with the original feature and qualifier columns removed
            and the features spread out over new columns named after the values
            of the qualifier columns.
        """
        df_copy = df.copy(deep=True)

        for feature in features:
            for i, row in df_copy.iterrows():
                qualifying_values = []
                for qualifier in qualifiers:
                    qualifier_value = row[qualifier]
                    # First, we need to replace some characters that can't be
                    #  present in pandas column names
                    qualifier_value = str(qualifier_value).replace("/", "-")

                    # qualityFlag is boolean, but it's value can be confusing
                    # if read without context, so "True" is replaced by
                    # "quality issue"
                    # and "False" by "no quality issue"
                    if qualifier == "qualityFlag":
                        qualifier_value = qualifier_value\
                            .replace("True", "quality_issue")\
                            .replace("False", "no_issue")

                    qualifying_values.append(qualifier_value)
                # Create a single qualifying string to append to the column
                # name
                qualifying_text = ".".join(qualifying_values)

                # get the actual value we want to place in a column
                feature_value = row[feature]

                # Get the full feature name
                feature_name = ".".join([qualifying_text, feature])

                # Save the dtype of the original feature
                feature_dtype = df[feature].dtype

                # if the column hasn't been created ytet, initialize it
                if feature_name not in df.columns:
                    df[feature_name] = None
                    df[feature_name] = df[feature_name].astype(feature_dtype)

                # Set the value in the new column
                df.loc[i, feature_name] = feature_value
        # Now that the information has been laid out in columns, the original
        # columns are redundant so they are deleted.
        columns_to_delete = features + qualifiers
        df.drop(columns=columns_to_delete, inplace=True)
        return df

    def __remove_access(self, df: pd.DataFrame) -> pd.DataFrame:
        """removes all columns that set access rights

        Parameters
        ----------
        df : pd.DataFrame
            The tabel with the access rights columns

        Returns
        -------
        pd.DataFrame
            The same table with the access rights columns removed.
        """
        to_remove = [col for col in df.columns if "access" in col.lower()]
        return df.drop(columns=to_remove)

    # Parsers to go from the standard ODM tables to a unified samples table
    def __parse_ww_measure(self) -> pd.DataFrame:
        """Prepares the WWMeasure Table for merging with
        the samples table to analyzer the data on a per-sample basis

        Returns
        -------
        pd.DataFrame
            Cleaned-up DataFrame indexed by sample.
            - Categorical columns from the WWMeasure table
                are separated into unique columns.
            - Boolean column's values are declared in the column title.
        """
        df = self.ww_measure

        # Breaking change in ODM. This line find the correct name
        # for the assayMethod ID column.
        assay_col = "assayID" if "assayID" in df.columns.to_list() \
            else "assayMethodID"

        df = self.__remove_access(df)
        df = self.__widen(
            df,
            features=[
                "value",
                "analysisDate",
                "reportDate",
                "notes",
                "qualityFlag",
                assay_col
            ],
            qualifiers=[
                "fractionAnalyzed",
                "type",
                "unit",
                "aggregation",
            ]
        )
        df = df.add_prefix("WWMeasure.")
        return df

    def __parse_site_measure(self) -> pd.DataFrame:
        df = self.site_measure

        df = self.__remove_access(df)
        df = self.__widen(
            df,
            features=[
                "value",
                "notes",
            ],
            qualifiers=[
                "type",
                "unit",
                "aggregation",
            ]
        )

        # Re-arrange the table so that it is arranges by dateTime, as this is
        # how site measures will be joined to samples
        df = df.groupby("dateTime").agg(utilities.reduce_by_type)
        df.reset_index(inplace=True)

        df = df.add_prefix("SiteMeasure.")
        return df

    def __parse_sample(self) -> pd.DataFrame:
        df = self.sample
        df_copy = df.copy(deep=True)

        # we want the sample to show up in any site where it is relevant.
        # Here, we gather all the siteIDs present in the siteID column for a
        # given sample, and we spread them over additional new rows so that in
        # the end, each row of the sample table has only one siteID
        for i, row in df_copy.iterrows():
            # Get the value of the siteID field
            sites = row["siteID"]
            # Check whether there are saveral ids in the field
            if ";" in sites:
                # Get all the site ids in the list
                site_ids = {x.strip() for x in sites.split(";")}
                # Assign one id to the original row
                df["siteID"].iloc[i] = site_ids.pop()
                # Create new rows for each additional siteID and assign them
                # each a siteID
                for site_id in site_ids:
                    new_row = df.iloc[i].copy()
                    new_row["siteID"] = site_id
                    df = df.append(new_row, ignore_index=True)
        # I will be copying sample.dateTime over to sample.dateTimeStart and
        #  sample.dateTimeEnd so that grab samples are seen in visualizations
        df["dateTimeStart"] = df["dateTimeStart"].fillna(df["dateTime"])
        df["dateTimeEnd"] = df["dateTimeEnd"].fillna(df["dateTime"])

        df.drop(columns=["dateTime"], inplace=True)

        df = df.add_prefix("Sample.")
        return df

    def __parse_site(self) -> pd.DataFrame:
        df = self.site
        df = df.add_prefix("Site.")
        return df

    def __parse_polygon(self) -> pd.DataFrame:
        df = self.polygon
        df = df.add_prefix("Polygon.")
        return df

    def __parse_cphd(self) -> pd.DataFrame:
        df = self.cphd

        df = self.__remove_access(df)
        df = self.__widen(
            df,
            features=[
                "value",
                "date",
                "notes"
            ],
            qualifiers=[
                "type",
                "dateType",
            ]
        )

        df = df.groupby("cphdID").agg(utilities.reduce_by_type)
        df.reset_index(inplace=True)
        df = df.add_prefix("CPHD.")
        return df

    def add_to_attr(self, attribute: str, new_df: pd.DataFrame) -> None:
        """Concatenate + set the value of attributes.

        Method that tries to concatenate the
        new value with the data already stored in the Odm attribute.
        """

        current_value = getattr(self, attribute)
        if current_value is None:
            setattr(self, attribute, new_df)
            return
        try:
            combined_df = current_value.append(new_df).drop_duplicates()
            setattr(self, attribute, combined_df)
        except Exception as e:
            print(e)
            setattr(self, attribute, current_value)
        return

    def get_attribute_from_name(self, name: str):
        """ Lookup from excel/sql name to python attribute

        Find the correct Odm attribute base on
        an Excel Sheet name or a SQL table name.
        """

        for attribute, dico in self.conversion_dict.items():
            if name in dico.values():
                return attribute
        return None

    def load_from_excel(
            self,
            filepath: str,
            sheet_names: list[int] = None
            ) -> None:
        """Reads an ODM-compatible excel file and loads the data into the Odm object.

        Parameters
        ----------
        filepath : str
            [description]
        sheet_names : [type], optional
            [description], by default None
        """

        if sheet_names is None:
            sheet_names = [
                self.conversion_dict[x]["excel_name"]
                for x in self.conversion_dict.keys()
            ]

        with warnings.catch_warnings():
            warnings.filterwarnings(action="ignore")
            xls = pd.read_excel(filepath, sheet_name=sheet_names)

        attributes_to_fill = [
            self.get_attribute_from_name(sheet_name)
            for sheet_name in sheet_names
        ]
        odm_names = [
            self.conversion_dict[attribute]["odm_name"]
            for attribute in attributes_to_fill
        ]

        for attribute, odm_name, sheet in zip(
            attributes_to_fill,
            odm_names,
            sheet_names,
        ):
            df = xls[sheet].copy(deep=True)
            # catch breaking change in data model
            if sheet == "WWMeasure" and "assayMethodID" in df.columns:
                df.rename(
                    columns={
                        "assayMethodID": "assayID"
                    },
                    inplace=True
                )
            type_cast_df = df.apply(
                lambda x: utilities.parse_types(odm_name, x),
                axis=0
            )
            self.add_to_attr(attribute, type_cast_df)
        return None

    def load_from_db(
        self,
        cnxn_str: str,
        table_names: list[str] = None
            ) -> None:
        """Loads data from a Ottawa Data Model compatible database into an ODM object

        Parameters
        ----------
        cnxn_str : str
            connextion string to the db
        table_names : list[str], optional
            Names of the tables you want to read in.
            By default None, in which case the function
            collects data from every table.
        """
        if table_names is None:
            table_names = [
                self.conversion_dict[attribute]["odm_name"]
                for attribute in self.conversion_dict.keys()
            ]

        engine = create_engine(cnxn_str)
        attributes_to_fill = [
            self.get_attribute_from_name(table_name)
            for table_name in table_names
        ]

        for attribute, table in zip(
            attributes_to_fill,
            table_names,
        ):
            df = pd.read_sql(f"select * from {table}", engine)
            type_cast_df = df.apply(
                lambda x: utilities.parse_types(table, x),
                axis=0
            )
            self.add_to_attr(attribute, type_cast_df)
        return None

    def get_geoJSON(self) -> dict:
        """Transforms the polygon Table into a geoJSON-like Python dictionary
        to ease mapping.

        Returns
        -------
        dict
            FeatureCollection dict with every defined polygon in the polygon
            table.
        """
        geo = {
            "type": "FeatureCollection",
            "features": []
        }
        polygon_df = self.polygon
        for i, row in polygon_df.iterrows():
            new_feature = {
                "type": "Feature",
                "geometry": utilities.convert_wkt_to_geojson(
                    row["wkt"]
                ),
                "properties": {
                    col:
                    row[col] for col in polygon_df.columns if "wkt" not in col
                },
                "id": i
            }
            geo["features"].append(new_feature)
        return geo

    def combine_per_sample(self) -> pd.DataFrame:
        """Combines data from all tables containing sample-related information
        into a single DataFrame.
        To simplify data mining, the categorical columns are separated into
        distinct columns.

        Returns
        -------
        pd.DataFrame
            DataFrame with each row representing a sample
        """
        # ________________
        # Helper functions
        def agg_ww_measure_per_sample(ww: pd.DataFrame) -> pd.DataFrame:
            """Helper function that aggregates the WWMeasure table by sample.

            Parameters
            ----------
            ww : pd.DataFrame
                The dataframe to rearrange. This dataframe should have gone
                through the __parse_ww_measure funciton before being passed in
                here. This is to ensure that categorical columns have been
                spread out.

            Returns
            -------
            pd.DataFrame
                DataFrame containing the data from the WWMeasure table,
                re-ordered so that each row represents a sample.
            """
            return ww\
                .groupby("WWMeasure.sampleID")\
                .agg(utilities.reduce_by_type)

        def combine_ww_measure_and_sample(
            ww: pd.DataFrame,
            sample: pd.DataFrame
                ) -> pd.DataFrame:
            """Merges tables on sampleID

            Parameters
            ----------
            ww : pd.DataFrame
                WWMeasure table re-organized by sample
            sample : pd.DataFrame
                The sample table

            Returns
            -------
            pd.DataFrame
                A combined table containing the data from both DataFrames
            """
            return pd.merge(
                sample, ww,
                how="left",
                left_on="Sample.sampleID",
                right_on="WWMeasure.sampleID")

        def combine_sample_site_measure(
            sample: pd.DataFrame,
            site_measure: pd.DataFrame
                ) -> pd.DataFrame:
            """Combines site measures and sample tables.

            Parameters
            ----------
            sample : pd.DataFrame
                sample DataFrame
            site_measure : pd.DataFrame
                Site Measure DataFrame

            Returns
            -------
            pd.DataFrame
                A combined DataFrame joined on sampling date
            """
            # Pandas doesn't provide good joining capability using dates, so we
            # go through SQLite to perform the join and come back to pandas
            # afterwards.

            # Make the db in memory
            conn = sqlite3.connect(':memory:')
            # write the tables
            sample.to_sql('sample', conn, index=False)
            site_measure.to_sql("site_measure", conn, index=False)

            # write the query
            qry = "select * from sample" + \
                " left join site_measure on" + \
                " [SiteMeasure.dateTime] between" + \
                " [Sample.dateTimeStart] and [Sample.dateTimeEnd]"
            merged = pd.read_sql_query(qry, conn)
            conn.close()
            return merged

        def combine_site_sample(
            sample: pd.DataFrame,
            site: pd.DataFrame
                ) -> pd.DataFrame:
            """Combines the sample table with site-specific data.

            Parameters
            ----------
            sample : pd.DataFrame
                The sample table
            site : pd.DataFrame
                The site table

            Returns
            -------
            pd.DataFrame
                A combined DataFrame joined on siteID
            """
            return pd.merge(
                sample,
                site,
                how="left",
                left_on="Sample.siteID",
                right_on="Site.siteID")

        def combine_cphd_by_geo(
            sample: pd.DataFrame,
            cphd: pd.DataFrame
                ) -> pd.DataFrame:
            """Return the cphd data relevant to a given dsample using the
            geographical intersection between the sample's sewershed polygon
            and the cphd's health region polygon.

            Parameters
            ----------
            sample : pd.DataFrame
                Table containg sample inform,ation as well as a site polygonID
            cphd : pd.DataFrame
                Table containing public health data and a polygonID.

            Returns
            -------
            pd.DataFrame
                Combined DataFrame containing bnoth sample data and public
                health data. The public health values are multiplied by a
                factor representing the percentage of the health region
                contained in the sewershed.
            """
            return merged

        # __________
        # Actual logic of the funciton
        ww_measure = self.__parse_ww_measure()
        ww_measure = agg_ww_measure_per_sample(ww_measure)

        sample = self.__parse_sample()
        merged = combine_ww_measure_and_sample(ww_measure, sample)

        site_measure = self.__parse_site_measure()
        merged = combine_sample_site_measure(merged, site_measure)

        site = self.__parse_site()
        merged = combine_site_sample(merged, site)

        cphd = self.__parse_cphd()
        merged = combine_cphd_by_geo(merged, cphd)

        merged.set_index("Sample.sampleID", inplace=True)

        return merged

    def save_to_db(
        self,
        df: pd.DataFrame,
        table_name: str,
        engine
            ) -> None:

        df.to_sql(
            name='myTempTable',
            con=engine,
            if_exists='replace',
            index=False
        )
        cols = df.columns
        cols_str = f"{tuple(cols)}".replace("'", "\"")
        with engine.begin() as cn:
            sql = f"""REPLACE INTO {table_name} {cols_str}
                SELECT * from myTempTable """
            cn.execute(sql)
            cn.execute("drop table if exists myTempTable")
        return

    def append_odm(self, other_odm):
        for attribute in self.__dict__:
            other_value = getattr(other_odm, attribute)
            self.add_to_attr(attribute, other_value)
        return


class OdmEncoder(json.JSONEncoder):
    def default(self, o):
        if (isinstance(o, Odm)):
            return {
                '__{}__'.format(o.__class__.__name__):
                o.__dict__
            }
        elif isinstance(o, pd.Timestamp):
            return {'__Timestamp__': str(o)}
        elif isinstance(o, pd.DataFrame):
            return {
                '__DataFrame__':
                o.to_json(date_format='iso', orient='split')
            }
        else:
            return json.JSONEncoder.default(self, o)


def decode_object(o):
    if '__Odm__' in o:
        a = Odm(
            o['__Odm__'],
        )
        a.__dict__.update(o['__Odm__'])
        return a

    elif '__DataFrame__' in o:
        a = pd.read_json(o['__DataFrame__'], orient='split')
        return(a)
    elif '__Timestamp__' in o:
        return pd.to_datetime(o['__Timestamp__'])
    else:
        return o


def create_db(filepath=None):
    url = "https://raw.githubusercontent.com/Big-Life-Lab/covid-19-wastewater/dev/src/wbe_create_table_SQLITE_en.sql"  # noqa
    sql = requests.get(url).text
    conn = None
    if filepath is None:
        filepath = "file::memory"
    try:
        conn = sqlite3.connect(filepath)
        conn.executescript(sql)

    except Exception as e:
        print(e)
    finally:
        if conn:
            conn.close()


def destroy_db(filepath):
    if os.path.exists(filepath):
        os.remove(filepath)


# testing functions
def test_samples_from_excel():
    # run with example excel data
    filename = "Data/Ville de Québec 202102.xlsx"
    odm_instance = Odm()
    odm_instance.load_from_excel(filename)
    geo = odm_instance.get_geoJSON()
    samples = odm_instance.combine_per_sample()
    return geo, samples


def test_samples_from_db():
    # run with example db data
    path = "Data/WBE.db"
    connection_string = f"sqlite:///{path}"
    odm_instance = Odm()
    odm_instance.load_from_db(connection_string)
    geo = odm_instance.get_geoJSON()
    return geo, odm_instance.combine_per_sample()


def test_from_excel_and_db():
    # run with example db data
    path = "Data/WBE.db"
    connection_string = f"sqlite:///{path}"
    odm_instance = Odm()
    filename = "Data/Ville de Québec 202102.xlsx"
    odm_instance.load_from_excel(filename)
    odm_instance.load_from_db(connection_string)
    geo = odm_instance.get_geoJSON()
    return geo, odm_instance.combine_per_sample()


def test_serialization_deserialization():
    # run with example db data
    odm_instance = Odm()
    filename = "Data/Ville de Québec 202102.xlsx"
    odm_instance.load_from_excel(filename)
    odm_instance.get_geoJSON()

    serialized = json.dumps(odm_instance, indent=4, cls=OdmEncoder)
    deserialized = json.loads(serialized, object_hook=decode_object)

    deserialized.combine_per_sample()


def test_visualization_helpers():
    wkts = []
    wkt_dir = "/workspaces/ODM Import/Data/polygons"
    for file in os.listdir(wkt_dir):
        if file.endswith(".wkt"):
            wkts.append(os.path.join(wkt_dir, file))
    polys = visualization_helpers.create_dummy_polygons(wkts)

    inst = Odm()
    inst.add_to_attr("polygon", polys)
    geo_json = inst.get_geoJSON()
    map_center = visualization_helpers.get_map_center(geo_json)
    zoom = visualization_helpers.get_zoom_level(geo_json, 800)
    print(zoom)
    return map_center, zoom


def test_finding_polygons():
    # run with example excel data
    filename = "Data/Ville de Québec 202102.xlsx"
    odm_instance = Odm()
    odm_instance.load_from_excel(filename)
    samples = odm_instance.combine_per_sample()
    geo = odm_instance.get_geoJSON()

    def get_polygon_name_from_agg_samples(
        odm_instance: Odm,
        df: pd.DataFrame
            ) -> pd.Series:
        poly_df = odm_instance.polygon
        df["Polygon.name"] = ""
        df.reset_index(inplace=True)
        for i, row in df.iterrows():
            poly_id = row["Site.polygonID"]
            poly_name = poly_df.loc[poly_df["polygonID"] == poly_id, "name"]
            df.iloc[i, df.columns.get_loc("Polygon.name")] = poly_name
        return df["Polygon.name"]

    poly_names = get_polygon_name_from_agg_samples(
        odm_instance, samples)

    def get_id_from_name_geojson(geo, name):
        features = geo["features"]
        for feature in features:
            if feature["properties"]["name"] == name:
                return feature["properties"]["polygonID"]

        return None

    poly_id = get_id_from_name_geojson(geo, "quebec est wwtp sewer catchment")
    return poly_names, poly_id


if __name__ == "__main__":

    # engine = create_db()
    # destroy_db(test_path)
    # samples = test_samples_from_excel()
    # samples = test_samples_from_db()
    # samples = test_from_excel_and_db()
    test_serialization_deserialization()
    test_visualization_helpers()
    test_finding_polygons()