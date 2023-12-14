# Automatic Broken Test Case Repair using Large Language Models


## Table of Contents
- [Introduction](#introduction)
- [Dataset Overview](#dataset-overview)
- [Study Replication Instructions](#study-replication-instructions)
- [Data Collection Instructions](#data-collection-instructions)


## Introduction
TODO: Define ATR and our contributions

### Publication
TODO: Add arxiv preprint


## Dataset Overview
We will publicly publish the dataset of this work once its paper is accepted.


## Study Replication Instructions

TODO: List python, java, maven versions
Install python packages using the following command:
```bash
pip install -r requirements.txt
```
TODO: Give an overview of the possible commands in the fine-tuning folder.
TODO: For each RQ, list all instructions in bash or python files.


## Data Collection Instructions
Run this command to build `jparser` (required to run the python scripts):
```bash
mvn clean package assembly:single -f jparser
```

First, run the following command to collect the repository's required raw data from GitHub:
```bash
python -u main.py gh_tags -r <repo> -o <output_path>
```
where the `<repo>` is the repository's (`<username>/<reponame>`, for example: `apache/spark`) and the `<output_path>` points to the path that the data is saved.

Then, the following command processes the raw data and creates the test case repair dataset (use the same `<repo>` and `<output_path>` as the previous command):
```bash
python -u main.py dataset -r <repo> -o <output_path>
```