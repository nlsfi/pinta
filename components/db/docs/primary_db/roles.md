# Primary DB roles & privileges

## Membership

```mermaid
flowchart LR
    subgraph groups [Group roles]
        pinta_backend[["pinta_backend"]]
        pinta_owner[["pinta_owner"]]
        pinta_processing_worker[["pinta_processing_worker"]]
        pinta_reader[["pinta_reader"]]
        pinta_writer[["pinta_writer"]]
    end
    subgraph users [Login users]
        admin(["admin"])
        backend_user(["backend_user"])
        processing_worker(["processing_worker"])
        qgis_editor(["qgis_editor"])
        qgis_viewer(["qgis_viewer"])
    end
    admin --> pinta_owner
    backend_user --> pinta_backend
    pinta_owner --> pinta_backend
    pinta_owner --> pinta_processing_worker
    pinta_owner --> pinta_reader
    pinta_owner --> pinta_writer
    pinta_processing_worker --> pinta_reader
    pinta_writer --> pinta_reader
    processing_worker --> pinta_processing_worker
    qgis_editor --> pinta_writer
    qgis_viewer --> pinta_reader
```

## Database privileges (`pinta`)

| Role | Privileges |
| --- | --- |
| `pinta_backend` | CONNECT, TEMPORARY |
| `pinta_owner` | CONNECT, TEMPORARY, CREATE |
| `pinta_processing_worker` | CONNECT, TEMPORARY |
| `pinta_reader` | CONNECT, TEMPORARY |
| `pinta_writer` | CONNECT, TEMPORARY |
| `admin` | CONNECT, TEMPORARY, CREATE |
| `backend_user` | CONNECT, TEMPORARY |
| `processing_worker` | CONNECT, TEMPORARY |
| `qgis_editor` | CONNECT, TEMPORARY |
| `qgis_viewer` | CONNECT, TEMPORARY |

## Schema privileges

| Role | `alembic` | `dem` | `management` | `processing` | `public` |
| --- | --- | --- | --- | --- | --- |
| `pinta_backend` | — | — | USAGE | — | USAGE |
| `pinta_owner` | USAGE, CREATE | USAGE, CREATE | USAGE, CREATE | USAGE, CREATE | USAGE, CREATE |
| `pinta_processing_worker` | — | USAGE, CREATE | USAGE | USAGE, CREATE | USAGE |
| `pinta_reader` | — | USAGE | USAGE | — | USAGE |
| `pinta_writer` | — | USAGE | USAGE | — | USAGE |
| `admin` | USAGE, CREATE | USAGE, CREATE | USAGE, CREATE | USAGE, CREATE | USAGE, CREATE |
| `backend_user` | — | — | USAGE | — | USAGE |
| `processing_worker` | — | USAGE, CREATE | USAGE | USAGE, CREATE | USAGE |
| `qgis_editor` | — | USAGE | USAGE | — | USAGE |
| `qgis_viewer` | — | USAGE | USAGE | — | USAGE |

## Default table privileges

| Grantee | Schema | Owner | Privileges |
| --- | --- | --- | --- |
| `pinta_owner` | `processing` | `pinta_processing_worker` | SELECT, INSERT, UPDATE, DELETE, TRUNCATE |
| `pinta_processing_worker` | `dem` | `pinta_owner` | SELECT, INSERT, UPDATE, DELETE, TRUNCATE |
| `pinta_processing_worker` | `management` | `pinta_owner` | SELECT, INSERT, UPDATE, DELETE, TRUNCATE |
| `pinta_processing_worker` | `processing` | `pinta_owner` | SELECT, INSERT, UPDATE, DELETE, TRUNCATE |
| `pinta_reader` | `dem` | `pinta_owner` | SELECT |
| `pinta_reader` | `management` | `pinta_owner` | SELECT |
| `pinta_writer` | `dem` | `pinta_owner` | SELECT, INSERT, UPDATE, DELETE, TRUNCATE |
| `pinta_writer` | `management` | `pinta_owner` | SELECT, INSERT, UPDATE, DELETE, TRUNCATE |
