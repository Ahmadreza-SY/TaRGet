# Broken Test Case Repair Using Language Models
## Setup Instructions
You need `java`, `maven`, and `python` to run this project.
Run this command to build `jparser` (required to run the python scripts):
```bash
mvn clean package assembly:single -f jparser
```
Install python packages using the following command:
```bash
pip install -r requirements.txt
```
## Data Collection
First, run the following command to collect the repository's required raw data from GitHub:
```bash
python -u main.py gh_tags -r <repo> -o <output_path>
```
where the `<repo>` is the repository's (`<username>/<reponame>`, for example: `apache/spark`) and the `<output_path>` points to the path that the data is saved.

Then, the following command processes the raw data and creates the test case repair dataset (use the same `<repo>` and `<output_path>` as the previous command):
```bash
python -u main.py dataset -r <repo> -o <output_path>
```