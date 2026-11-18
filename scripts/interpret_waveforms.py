import argparse,json
from pathlib import Path
from circuit_agent.tools import analyze_csv,parse_log
def main():
 p=argparse.ArgumentParser();p.add_argument("--log");p.add_argument("--csv");p.add_argument("--out",default="waveform_report.json");a=p.parse_args(); measurements,warnings=(parse_log(Path(a.log)) if a.log else ([],[])); Path(a.out).write_text(json.dumps({"measurements":measurements,"warnings":warnings},indent=2));print(a.out)
if __name__=="__main__":main()
