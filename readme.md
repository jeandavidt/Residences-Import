# Protocole ODM Import Thomas

Do Date: October 14, 2021
Done: No

1. Install anaconda on your computer.
2. Copy the directory to your computer.
3. Open the Anaconda prompt and navigate to the project directory using the command:

    ```bash
    cd /path/to/project/directory
    ```

4. Create a new conda environment named `residences` using the command:

    ```bash
    conda env create --file environment.yml --name residences
    ```

5. Activate the new environment using the command:

    ```bash
    conda activate residences
    ```

6. Insert the static file and the lab data file in the `Input` subfolder.
7. Run the script using the command:

    ```bash
    python runscript.py
    ```

8. The resulting ODM-compatible files will be placed in the `Output` folder.
