# Unit Tests for DAG Files

DAGs are created dynamically in tests using DAG factory functions. **Note! In all tests where the `sync_bag_to_db` function is called, a unique `dag_id` must be used.** Otherwise, the mocks will not work correctly.

```python
import uuid
def create_dag_to_test() -> "DAG":
    # Create a unique dag_id
    dag = create_x_dag(
        dag_id=f"some_id_{uuid.uuid4()}"
    )

    dag_bag = DagBag(include_examples=False)
    dag_bag.bag_dag(dag)
    sync_bag_to_db(dag_bag, "mock-dags", None)

    return dag
```

A pytest fixture cannot be used for this (it must be done with a regular function) because mocks will not work if they are created after the DAG has already been instantiated. Therefore, the `create_dag_to_test` function must be called only after the mocks have been defined in the tests.

```python
def test_something(mocker: "MockerFixture"):
    mock_something = mocker.patch("some.function")

    # Mocks must be created before calling create_dag_to_test
    dag = create_dag_to_test()
    dag.test()
```
