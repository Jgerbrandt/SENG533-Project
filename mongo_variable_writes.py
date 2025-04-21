from pymongo import MongoClient
from prometheus_client import start_http_server, Summary, Counter
import time
import random
import string

# seperate summarys for each config
one_kb_60_false_time = Summary(
    'mongo_one_kb_60_false_duration_seconds',
    'Time spent on MongoDB one_kb_60_false write operations'
)
ten_kb_60_false_time = Summary(
    'mongo_ten_kb_60_false_duration_seconds',
    'Time spent on MongoDB ten_kb_60_false write operations'
)
twenty_kb_60_false_time = Summary(
    'mongo_twenty_kb_60_false_duration_seconds',
    'Time spent on MongoDB twenty_kb_60_false write operations'
)
fifty_kb_60_false_time = Summary(
    'mongo_fifty_kb_60_false_duration_seconds',
    'Time spent on MongoDB fifty_kb_60_false write operations'
)
one_hundred_kb_60_false_time = Summary(
    'mongo_one_hundred_kb_60_false_duration_seconds',
    'Time spent on MongoDB one_hundred_kb_60_false write operations'
)

one_kb_60_true_time = Summary(
    'mongo_one_kb_60_true_duration_seconds',
    'Time spent on MongoDB one_kb_60_true write operations'
)
ten_kb_60_true_time = Summary(
    'mongo_ten_kb_60_true_duration_seconds',
    'Time spent on MongoDB ten_kb_60_true write operations'
)
twenty_kb_60_true_time = Summary(
    'mongo_twenty_kb_60_true_duration_seconds',
    'Time spent on MongoDB twenty_kb_60_true write operations'
)
fifty_kb_60_true_time = Summary(
    'mongo_fifty_kb_60_true_duration_seconds',
    'Time spent on MongoDB fifty_kb_60_true write operations'
)
one_hundred_kb_60_true_time = Summary(
    'mongo_one_hundred_kb_60_true_duration_seconds',
    'Time spent on MongoDB one_hundred_kb_60_true write operations'
)

def generate_random_string(size):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=size))

def test_variable_data_size_mongo(timer, collection, size_kb, duration_seconds, multiple_types=False):
    # Test write operations with variable data sizes, duration, and data types
    start_time = time.time()
    try:
        while time.time() - start_time < duration_seconds:
            data_size = size_kb * 1024 
            if multiple_types:
                # multiple dtypes
                other_fields_size = (
                    4 +  # size of age
                    1 +  # is_active bool
                    5 * 10 +  # tags
                    40  # metadata
                )
                # rest of the size goes to name
                name_size = max(0, data_size - other_fields_size)
                large_data = {
                    "name": generate_random_string(name_size),
                    "age": random.randint(18, 80),
                    "is_active": random.choice([True, False]),
                    "tags": [generate_random_string(10) for _ in range(5)],
                    "metadata": {"key": generate_random_string(20), "value": generate_random_string(20)}
                }
            else:
                # single dtype
                large_data = {"name": generate_random_string(data_size)}

            with timer.time():
                collection.insert_one(large_data)
    except Exception as e:
        print(f"Failed to insert document {e}")

def test_batch_writes_mongo(timer, collection, size_kb, duration_seconds, batch_size, multiple_types=False):
    # test batch write operations with variable data sizes, duration, and data types.
    start_time = time.time()
    try:
        while time.time() - start_time < duration_seconds:
            batch = []
            for _ in range(batch_size):
                data_size = size_kb * 1024
                # multiple dtypes
                if multiple_types:
                    other_fields_size = (
                        4 +  # size of age
                        1 +  # is_active bool
                        5 * 10 +  # tags
                        40  # metadata
                    )
                    # rest of the size goes to name
                    name_size = max(0, data_size - other_fields_size)
                    large_data = {
                        "name": generate_random_string(name_size),
                        "age": random.randint(18, 80),
                        "is_active": random.choice([True, False]),
                        "tags": [generate_random_string(10) for _ in range(5)],
                        "metadata": {"key": generate_random_string(20), "value": generate_random_string(20)}
                    }
                else:
                    # single dtype
                    large_data = {"name": generate_random_string(data_size)}

                batch.append(large_data)

            # batch insert
            with timer.time():
                collection.insert_many(batch)
    except Exception as e:
        print(f"Failed to insert batch: {e}")

def main():
    start_http_server(8000)
    print("Prometheus metrics available at http://localhost:8000/metrics")

    uri = "mongodb://localhost:27017/"
    client = MongoClient(uri)

    db = client["test_db"]

    for collection_name in db.list_collection_names():
        db.drop_collection(collection_name)

    # a new table for each test
    one_kb_60_false = db["write1"]
    ten_kb_60_false = db["write2"]
    twenty_kb_60_false = db["write3"]
    fifty_kb_60_false = db["write4"]
    one_hundred_kb_60_false = db["write5"]

    one_kb_60_true = db["write6"]
    ten_kb_60_true = db["write7"]
    twenty_kb_60_true = db["write8"]
    fifty_kb_60_true = db["write9"]
    one_hundred_kb_60_true = db["write10"]
    
    # tests with different data sizes and types for 60 seconds
    test_variable_data_size_mongo(one_kb_60_false_time, one_kb_60_false, size_kb=1, duration_seconds=60, multiple_types=False)
    test_variable_data_size_mongo(ten_kb_60_false_time, ten_kb_60_false, size_kb=10, duration_seconds=60, multiple_types=False)
    test_variable_data_size_mongo(twenty_kb_60_false_time,  twenty_kb_60_false, size_kb=20, duration_seconds=60, multiple_types=False)
    test_variable_data_size_mongo(fifty_kb_60_false_time, fifty_kb_60_false, size_kb=50, duration_seconds=60, multiple_types=False)
    test_variable_data_size_mongo(one_hundred_kb_60_false_time, one_hundred_kb_60_false, size_kb=100, duration_seconds=60, multiple_types=False)

    test_variable_data_size_mongo(one_kb_60_true_time, one_kb_60_true, size_kb=1, duration_seconds=60, multiple_types=True)
    test_variable_data_size_mongo(ten_kb_60_true_time, ten_kb_60_true, size_kb=10, duration_seconds=60, multiple_types=True)
    test_variable_data_size_mongo(twenty_kb_60_true_time, twenty_kb_60_true, size_kb=20, duration_seconds=60, multiple_types=True)
    test_variable_data_size_mongo(fifty_kb_60_true_time, fifty_kb_60_true, size_kb=50, duration_seconds=60, multiple_types=True)
    test_variable_data_size_mongo(one_hundred_kb_60_true_time, one_hundred_kb_60_true, size_kb=100, duration_seconds=60, multiple_types=True)

if __name__ == "__main__":
    main()
    while True:
        time.sleep(10)