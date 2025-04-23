import os
import uuid
import time
import random
import string
from cassandra.cluster import Cluster
from prometheus_client import start_http_server, Summary, Counter

from cassandra.query import BatchStatement, SimpleStatement, BatchType
from cassandra.concurrent import execute_concurrent_with_args

os.environ["CASSANDRA_DRIVER_EVENT_LOOP"] = "asyncio"

cluster = Cluster(['localhost'])
session = cluster.connect()


session.execute("""
    CREATE KEYSPACE IF NOT EXISTS test
    WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
""")
session.set_keyspace('test')

for i in range(1, 11):
    session.execute(f"""
        CREATE TABLE IF NOT EXISTS write{i} (
            id UUID PRIMARY KEY,
            name text,
            age int,
            is_active boolean,
            tags list<text>,
            metadata map<text, text>
        )
    """)
    session.execute(f"""
        CREATE INDEX IF NOT EXISTS ON write{i} (is_active)
    """)
    session.execute(f"""
        CREATE INDEX IF NOT EXISTS ON write{i} (age)
    """)


def define_metrics(prefix):
    return {
        "time": Summary(f'cassandra_{prefix}_duration_seconds', f'Time spent on Cassandra {prefix} write operations')
    }

metric_sets = {
    "one_kb_100_batch_false": define_metrics("one_kb_100_batch_false"),
    "ten_kb_100_batch_false": define_metrics("ten_kb_100_batch_false"),
    "twenty_kb_100_batch_false": define_metrics("twenty_kb_100_batch_false"),
    "fifty_kb_100_batch_false": define_metrics("fifty_kb_100_batch_false"),
    "one_hundred_kb_100_batch_false": define_metrics("one_hundred_kb_100_batch_false"),
    "one_kb_100_batch_true": define_metrics("one_kb_100_batch_true"),
    "ten_kb_100_batch_true": define_metrics("ten_kb_100_batch_true"),
    "twenty_100_batch_true": define_metrics("twenty_100_batch_true"),
    "fifty_kb_100_batch_true": define_metrics("fifty_kb_100_batch_true"),
    "one_hundred_kb_100_batch_true": define_metrics("one_hundred_kb_100_batch_true"),
}


# metric_sets = {
#     "one_kb_30_false": define_metrics("one_kb_30_false"),
#     "ten_kb_30_false": define_metrics("ten_kb_30_false"),
#     "twenty_kb_30_false": define_metrics("twenty_kb_30_false"),
#     "fifty_kb_30_false": define_metrics("fifty_kb_30_false"),
#     "one_hundred_kb_30_false": define_metrics("one_hundred_kb_30_false"),
#     "one_kb_30_true": define_metrics("one_kb_30_true"),
#     "ten_kb_30_true": define_metrics("ten_kb_30_true"),
#     "twenty_kb_30_true": define_metrics("twenty_kb_30_true"),
#     "fifty_kb_30_true": define_metrics("fifty_kb_30_true"),
#     "one_hundred_kb_30_true": define_metrics("one_hundred_kb_30_true"),
# }

def generate_random_string(size):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=size))

def test_query_performance_cassandra(timer, table_name, duration_seconds, complex_query=False):
    start_time = time.time()
    try:
        while time.time() - start_time < duration_seconds:
            if complex_query:
                # complex query with indexed fields
                query = f"""
                    SELECT name, age, tags FROM {table_name}
                    WHERE is_active = True AND age >= 30
                    LIMIT 10
                """
                with timer.time():
                    rows = session.execute(query)
                    results = list(rows)
            else:
                # simple query using indexed field
                query = f"""
                    SELECT * FROM {table_name}
                    WHERE is_active = True
                    LIMIT 1
                """
                with timer.time():
                    result = session.execute(query).one()
    except Exception as e:
        print(f"Failed to execute query: {e}")

def populate_table_with_data(table_name, num_records=1000):
    for _ in range(num_records):
        id = uuid.uuid4()
        name = generate_random_string(random.randint(5, 50))
        age = random.randint(18, 80)
        is_active = random.choice([True, False])
        tags = [generate_random_string(10) for _ in range(random.randint(1, 10))]
        metadata = {"key": generate_random_string(20), "value": generate_random_string(20)}
        created_at = time.time() - random.randint(0, 31536000)
        data = generate_random_string(random.randint(100, 1024))

        query = f"""
            INSERT INTO {table_name} (id, name, age, is_active, tags, metadata, created_at, data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (id, name, age, is_active, tags, metadata, created_at, data)
        session.execute(query, values)

# def test_batch_writes_cassandra(timer, table_name, size_kb, duration_seconds, batch_size, multiple_types=False):
#     start_time = time.time()
#     try:
#         while time.time() - start_time < duration_seconds:
#             batch_query = "BEGIN UNLOGGED BATCH "
#             batch_values = []
#             for _ in range(batch_size):
#                 data_size = size_kb * 1024
#                 id = uuid.uuid4()

#                 if multiple_types:
#                     other_fields_size = (
#                         4 +  # age
#                         1 +  # is_active
#                         5 * 10 +  # tags
#                         40  # metadata
#                     )
#                     name_size = max(0, data_size - other_fields_size)
#                     name = generate_random_string(name_size)
#                     age = random.randint(18, 80)
#                     is_active = random.choice([True, False])
#                     tags = [generate_random_string(10) for _ in range(5)]
#                     metadata = {"key": generate_random_string(20), "value": generate_random_string(20)}

#                     query = f"""
#                         INSERT INTO {table_name} (id, name, age, is_active, tags, metadata)
#                         VALUES (%s, %s, %s, %s, %s, %s);
#                     """
#                     batch_query += query
#                     batch_values.extend([id, name, age, is_active, tags, metadata])
#                 else:
#                     name = generate_random_string(data_size)
#                     query = f"""
#                         INSERT INTO {table_name} (id, name)
#                         VALUES (%s, %s);
#                     """
#                     batch_query += query
#                     batch_values.extend([id, name])

#             batch_query += "APPLY BATCH"

#             with timer.time():
#                 session.execute(batch_query, batch_values)
#     except Exception as e:
#         print(f"Failed to insert batch into {table_name}: {e}")

def test_batch_writes_cassandra(timer, table_name, size_kb, duration_seconds, batch_size, multiple_types=False):
    if multiple_types:
        insert_stmt = session.prepare(f"""
            INSERT INTO {table_name} (id, name, age, is_active, tags, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """)
    else:
        insert_stmt = session.prepare(f"""
            INSERT INTO {table_name} (id, name)
            VALUES (?, ?)
        """)

    start_time = time.time()
    try:
        while time.time() - start_time < duration_seconds:
            parameters = []

            for _ in range(batch_size):
                id = uuid.uuid4()
                data_size = size_kb * 1024

                if multiple_types:
                    other_fields_size = (
                        4 +  # age
                        1 +  # is_active
                        5 * 10 +  # tags
                        40  # metadata
                    )
                    name_size = max(0, data_size - other_fields_size)
                    name = generate_random_string(name_size)
                    age = random.randint(18, 80)
                    is_active = random.choice([True, False])
                    tags = [generate_random_string(10) for _ in range(5)]
                    metadata = {"key": generate_random_string(20), "value": generate_random_string(20)}
                    parameters.append((id, name, age, is_active, tags, metadata))
                else:
                    name = generate_random_string(data_size)
                    parameters.append((id, name))

            with timer.time():
                execute_concurrent_with_args(session, insert_stmt, parameters, concurrency=batch_size)

    except Exception as e:
        print(f"Failed to insert rows into {table_name}: {e}")





def test_variable_data_size_cassandra(timer, table_name, size_kb, duration_seconds, multiple_types=False):
    start_time = time.time()
    try:
        while time.time() - start_time < duration_seconds:
            data_size = size_kb * 1024
            id = uuid.uuid4()

            if multiple_types:
                other_fields_size = (
                    4 +  # age
                    1 +  # is_active
                    5 * 10 +  # tags
                    40  # metadata
                )
                name_size = max(0, data_size - other_fields_size)
                name = generate_random_string(name_size)
                tags = [generate_random_string(10) for _ in range(5)]
                metadata = {
                    "key": generate_random_string(20),
                    "value": generate_random_string(20)
                }
                query = f"""
                    INSERT INTO {table_name} (id, name, age, is_active, tags, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                values = (id, name, random.randint(18, 80), random.choice([True, False]), tags, metadata)
            else:
                name = generate_random_string(data_size)
                query = f"""
                    INSERT INTO {table_name} (id, name)
                    VALUES (%s, %s)
                """
                values = (id, name)

            with timer.time():
                session.execute(query, values)
    except Exception as e:
        print(f"Failed to insert into {table_name}: {e}")


def main():
    start_http_server(8000)
    print("Prometheus metrics available at http://localhost:8000/metrics")

    #populate_table_with_data("write6", num_records=1000)
    #query_metric = Summary('cassandra_query_duration_seconds', 'Time spent on Cassandra query operations')
    # test_variable_data_size_cassandra(metric_sets["one_kb_300_false"]["time"], "write1", 1, 300, multiple_types=False)
    # test_variable_data_size_cassandra(metric_sets["ten_kb_300_false"]["time"], "write2", 10, 300, multiple_types=False)
    # test_variable_data_size_cassandra(metric_sets["twenty_kb_300_false"]["time"], "write3", 20, 300, multiple_types=False)
    # test_variable_data_size_cassandra(metric_sets["fifty_kb_300_false"]["time"], "write4", 50, 300, multiple_types=False)
    # test_variable_data_size_cassandra(metric_sets["one_hundred_kb_300_false"]["time"], "write5", 100, 300, multiple_types=False)

    # test_variable_data_size_cassandra(metric_sets["one_kb_300_true"]["time"], "write6", 1, 300, multiple_types=True)
    # test_variable_data_size_cassandra(metric_sets["ten_kb_300_true"]["time"], "write7", 10, 300, multiple_types=True)
    # test_variable_data_size_cassandra(metric_sets["twenty_kb_300_true"]["time"], "write8", 20, 300, multiple_types=True)
    # test_variable_data_size_cassandra(metric_sets["fifty_kb_300_true"]["time"], "write9", 50, 300, multiple_types=True)
    # test_variable_data_size_cassandra(metric_sets["one_hundred_kb_300_true"]["time"], "write10", 100, 300, multiple_types=True)

    # Uncomment the following lines to test batch writes
    test_batch_writes_cassandra(metric_sets["one_kb_100_batch_false"]["time"], "write1", 1, 300, batch_size=100, multiple_types=False)
    print("Batch write 1 KB completed")
    test_batch_writes_cassandra(metric_sets["ten_kb_100_batch_false"]["time"], "write2", 10, 300, batch_size=100, multiple_types=False)
    print("Batch write 10 KB completed")
    test_batch_writes_cassandra(metric_sets["twenty_kb_100_batch_false"]["time"], "write3", 20, 300, batch_size=100, multiple_types=False)
    print("Batch write 20 KB completed")
    test_batch_writes_cassandra(metric_sets["fifty_kb_100_batch_false"]["time"], "write4", 50, 300, batch_size=100, multiple_types=False)
    print("Batch write 50 KB completed")
    test_batch_writes_cassandra(metric_sets["one_hundred_kb_100_batch_false"]["time"], "write5", 100, 300, batch_size=100, multiple_types=False)
    print("Batch write 100 KB completed")

    test_batch_writes_cassandra(metric_sets["one_kb_100_batch_true"]["time"], "write6", 1, 300, batch_size=100, multiple_types=True)
    print("Batch write 1 KB with multiple types completed")
    test_batch_writes_cassandra(metric_sets["ten_kb_100_batch_true"]["time"], "write7", 10, 300, batch_size=100, multiple_types=True)
    print("Batch write 10 KB with multiple types completed")
    test_batch_writes_cassandra(metric_sets["twenty_100_batch_true"]["time"], "write8", 20, 300, batch_size=100, multiple_types=True)
    print("Batch write 20 KB with multiple types completed")
    test_batch_writes_cassandra(metric_sets["fifty_kb_100_batch_true"]["time"], "write9", 50, 300, batch_size=100, multiple_types=True)
    print("Batch write 50 KB with multiple types completed")
    test_batch_writes_cassandra(metric_sets["one_hundred_kb_100_batch_true"]["time"], "write10", 100, 300, batch_size=100, multiple_types=True)
    print("Batch write 100 KB with multiple types completed")

    # Uncomment the following lines to test query performance
    # test_query_performance_cassandra(metric_sets["one_kb_30_false"]["time"], "write1", 30, complex_query=False)
    # test_query_performance_cassandra(metric_sets["ten_kb_30_false"]["time"], "write2", 30, complex_query=False)
    # test_query_performance_cassandra(metric_sets["twenty_kb_30_false"]["time"], "write3", 30, complex_query=False)
    # test_query_performance_cassandra(metric_sets["fifty_kb_30_false"]["time"], "write4", 30, complex_query=False)
    # test_query_performance_cassandra(metric_sets["one_hundred_kb_30_false"]["time"], "write5", 30, complex_query=False)

    # test_query_performance_cassandra(metric_sets["one_kb_30_true"]["time"], "write6", 30, complex_query=True)
    # test_query_performance_cassandra(metric_sets["ten_kb_30_true"]["time"], "write7", 30, complex_query=True)
    # test_query_performance_cassandra(metric_sets["twenty_kb_30_true"]["time"], "write8", 30, complex_query=True)
    # test_query_performance_cassandra(metric_sets["fifty_kb_30_true"]["time"], "write9", 30, complex_query=True)
    # test_query_performance_cassandra(metric_sets["one_hundred_kb_30_true"]["time"], "write10", 30, complex_query=True)




    print("TEST COMPLETED")

if __name__ == "__main__":
    main()
    while True:
        time.sleep(10)
