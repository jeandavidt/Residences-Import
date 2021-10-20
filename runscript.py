import argparse
import os
import shutil
import yaml
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from easydict import EasyDict
from plotly.express import colors as pc
from plotly.subplots import make_subplots

# from config import *
from wbe_odm import odm, utilities
from wbe_odm.odm_mappers import (csv_folder_mapper, inspq_mapper,
                                 mcgill_mapper, modeleau_mapper, vdq_mapper)




def load_files_from_folder(folder, extension):
    files = os.listdir(folder)
    return [file for file in files if "$" not in file and extension in file]





if __name__ == "__main__":
    # Arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', type=str, default='config.yaml', help="Config file where all the paths are defined")  # noqa
    args = parser.parse_args()

    config = args.config

    if config:
        with open(config, "r") as f:
            config = EasyDict(yaml.safe_load(f))

    if not os.path.exists(config.csv_folder):
        raise ValueError(
            "Output folder for csv's does not exist. Please modify config file.")

    store = odm.Odm()
    static_path = os.path.join(config.data_folder, config.static_data)
 

    print("Importing viral data...")
    lab = mcgill_mapper.McGillMapper()
    virus_path = os.path.join(config.data_folder, config.virus_data)

    lab.read(virus_path, static_path, config.virus_sheet_name, config.virus_lab)  # noqa
    store.append_from(lab)


    print("Removing older dataset...")
    for root, dirs, files in os.walk(config.csv_folder):
        for f in files:
            os.unlink(os.path.join(root, f))
        for d in dirs:
            shutil.rmtree(os.path.join(root, d))

    print("Saving dataset...")
    store.to_csv(config.csv_folder)
    print(f"Saved to folder {config.csv_folder}")
