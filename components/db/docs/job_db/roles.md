# Job DB roles & privileges

## Membership

```mermaid
flowchart LR
    subgraph groups [Group roles]
        pinta_owner[["pinta_owner"]]
        pinta_processing_worker[["pinta_processing_worker"]]
        pinta_reader[["pinta_reader"]]
        pinta_writer[["pinta_writer"]]
    end
    subgraph users [Login users]
        admin(["admin"])
        processing_worker(["processing_worker"])
        qgis_editor(["qgis_editor"])
        qgis_viewer(["qgis_viewer"])
    end
    admin --> pinta_owner
    pinta_owner --> pinta_processing_worker
    pinta_owner --> pinta_reader
    pinta_owner --> pinta_writer
    pinta_processing_worker --> pinta_reader
    pinta_writer --> pinta_reader
    processing_worker --> pinta_processing_worker
    qgis_editor --> pinta_writer
    qgis_viewer --> pinta_reader
```

## Database privileges (`job_template`)

| Role | Privileges |
| --- | --- |
| `pinta_owner` | CONNECT, TEMPORARY, CREATE |
| `pinta_processing_worker` | CONNECT, TEMPORARY |
| `pinta_reader` | CONNECT, TEMPORARY |
| `pinta_writer` | CONNECT, TEMPORARY |
| `admin` | CONNECT, TEMPORARY, CREATE |
| `processing_worker` | CONNECT, TEMPORARY |
| `qgis_editor` | CONNECT, TEMPORARY |
| `qgis_viewer` | CONNECT, TEMPORARY |

## Schema privileges

| Role | `alembic` | `public` | `reference` | `user_data` |
| --- | --- | --- | --- | --- |
| `pinta_owner` | USAGE, CREATE | USAGE, CREATE | USAGE, CREATE | USAGE, CREATE |
| `pinta_processing_worker` | — | USAGE | USAGE | USAGE |
| `pinta_reader` | — | USAGE | USAGE | USAGE |
| `pinta_writer` | — | USAGE | USAGE | USAGE |
| `admin` | USAGE, CREATE | USAGE, CREATE | USAGE, CREATE | USAGE, CREATE |
| `processing_worker` | — | USAGE | USAGE | USAGE |
| `qgis_editor` | — | USAGE | USAGE | USAGE |
| `qgis_viewer` | — | USAGE | USAGE | USAGE |

## Default table privileges

| Grantee | Schema | Owner | Privileges |
| --- | --- | --- | --- |
| `pinta_processing_worker` | `reference` | `pinta_owner` | SELECT, INSERT, UPDATE, DELETE, TRUNCATE |
| `pinta_processing_worker` | `user_data` | `pinta_owner` | SELECT, INSERT, UPDATE, DELETE, TRUNCATE |
| `pinta_reader` | `reference` | `pinta_owner` | SELECT |
| `pinta_reader` | `user_data` | `pinta_owner` | SELECT |
| `pinta_writer` | `reference` | `pinta_owner` | SELECT, INSERT, UPDATE, DELETE, TRUNCATE |
| `pinta_writer` | `user_data` | `pinta_owner` | SELECT, INSERT, UPDATE, DELETE, TRUNCATE |
