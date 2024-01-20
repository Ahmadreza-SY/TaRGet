# TaRGet: Automated Test Case Repair Using Large Language Models


## Table of Contents
- [Introduction](#introduction)
- [Dataset Overview](#dataset-overview)
- [Study Replication Instructions](#study-replication-instructions)
- [Data Collection Instructions](#data-collection-instructions)

## Introduction
In this work, we introduce TaRGet and TaRBench, both of which are elaborated on in the subsequent sections.

### TaRGet
Ensuring the quality of software systems through testing is a critical aspect of software development. However, the maintenance of test cases presents significant challenges, both in terms of complexity and cost. The constant need for updates to align with evolving systems under test can result in broken test cases, leading to a deterioration in test suite quality and disruptions in the software development process. To address these challenges, we introduce TaRGet (Test Repair GEneraTor), an approach that leverages pre-trained code language models for automated test case repair. TaRGet treats test repair as a language translation task and employs a two-step process to fine-tune a language model using essential context data that characterizes test breakages.

<!-- ### Publication
TODO: Add once published -->


### TaRBench
TaRBench is a comprehensive benchmark that we developed to evaluate the effectiveness of TaRGet in automated test case repair. The benchmark encompasses 45,373 broken test repairs across 59 open-source projects, providing a diverse and extensive dataset for assessing the capabilities of TaRGet. TaRBench data and detailed information can be accessed at: https://figshare.com/s/77598ce966e625c75f5a


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