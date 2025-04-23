import re
import csv

def parse_prometheus_metrics(file_path):
    metrics = {}
    current_metric = None

    with open(file_path, 'r') as file:
        for line in file:
            if line.startswith("# HELP"):
                match = re.match(r"# HELP (\S+) (.+)", line)
                if match:
                    current_metric = match.group(1)
                    metrics[current_metric] = {"description": match.group(2), "count": None, "sum": None}

            elif current_metric and not line.startswith("#"):
                if "count" in line:
                    match = re.match(r"(\S+)\s+([\d\.e\+]+)", line)
                    if match and "count" in match.group(1):
                        metrics[current_metric]["count"] = float(match.group(2))
                elif "sum" in line:
                    match = re.match(r"(\S+)\s+([\d\.e\+]+)", line)
                    if match and "sum" in match.group(1):
                        metrics[current_metric]["sum"] = float(match.group(2))

    metrics = {key: value for key, value in metrics.items() if value["count"] is not None and value["sum"] is not None}

    return metrics

def save_metrics_to_csv(metrics, output_file):
    with open(output_file, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Description", "Count", "Sum"])
        for metric, details in metrics.items():
            writer.writerow([details["description"], details["count"], details["sum"]])

def main():
    input_file = "./prometheus-outputs/cassandra/batch_write/txt/cassandra_300_seconds_batch_run_1.txt"
    output_csv = input_file.replace("txt", "csv")

    metrics = parse_prometheus_metrics(input_file)

    save_metrics_to_csv(metrics, output_csv)

if __name__ == "__main__":
    main()