// Controller-owned launcher-matched QE rank wrapper.
// It is compiled inside the Slurm allocation and launched by the same
// production mpirun command that ultimately executes pw.x.

#include <cuda_runtime.h>

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#ifndef PATH_MAX
#define PATH_MAX 4096
#endif

static void die(const char *message) {
    fprintf(stderr, "qe_rank_wrapper ERROR: %s\n", message);
    exit(40);
}

static const char *need_env(const char *name) {
    const char *value = getenv(name);
    if (value == NULL || value[0] == '\0') {
        fprintf(stderr, "qe_rank_wrapper ERROR: missing env %s\n", name);
        exit(41);
    }
    return value;
}

static int env_int_any(const char **names, int fallback) {
    for (int i = 0; names[i] != NULL; ++i) {
        const char *value = getenv(names[i]);
        if (value != NULL && value[0] != '\0') {
            return atoi(value);
        }
    }
    return fallback;
}

static void json_escape(FILE *f, const char *value) {
    if (value == NULL) value = "";
    for (const unsigned char *p = (const unsigned char *)value; *p; ++p) {
        if (*p == '"' || *p == '\\') {
            fputc('\\', f);
            fputc(*p, f);
        } else if (*p == '\n') {
            fputs("\\n", f);
        } else if (*p == '\r') {
            fputs("\\r", f);
        } else if (*p == '\t') {
            fputs("\\t", f);
        } else if (*p < 0x20) {
            fprintf(f, "\\u%04x", *p);
        } else {
            fputc(*p, f);
        }
    }
}

static void choose_cuda_visible_device(int local_rank, char *selected, size_t selected_size) {
    const char *orig = getenv("CUDA_VISIBLE_DEVICES");
    if (orig == NULL || orig[0] == '\0') {
        snprintf(selected, selected_size, "%d", local_rank);
        return;
    }

    char copy[1024];
    snprintf(copy, sizeof(copy), "%s", orig);
    int index = 0;
    char *save = NULL;
    for (char *tok = strtok_r(copy, ",", &save); tok != NULL; tok = strtok_r(NULL, ",", &save), ++index) {
        if (index == local_rank) {
            snprintf(selected, selected_size, "%s", tok);
            return;
        }
    }
    snprintf(selected, selected_size, "%d", local_rank);
}

static void write_record(
    const char *records_dir,
    int rank,
    int local_rank,
    int mpi_size,
    int cuda_count,
    const char *uuid,
    const char *pci_bus_id,
    const char *hostname_value,
    const char *original_cvd,
    const char *active_cvd
) {
    char tmp_path[PATH_MAX];
    char final_path[PATH_MAX];
    snprintf(tmp_path, sizeof(tmp_path), "%s/rank_%d.json.tmp.%ld", records_dir, rank, (long)getpid());
    snprintf(final_path, sizeof(final_path), "%s/rank_%d.json", records_dir, rank);
    FILE *f = fopen(tmp_path, "w");
    if (!f) die("cannot create mapping record temp file");

    time_t now = time(NULL);
    struct tm tm_value;
    gmtime_r(&now, &tm_value);
    char timestamp[64];
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", &tm_value);

    fprintf(f, "{\n");
    fprintf(f, "  \"schema_version\": \"hipac26_qe_launcher_mapping_v1\",\n");
    fprintf(f, "  \"hostname\": \""); json_escape(f, hostname_value); fprintf(f, "\",\n");
    fprintf(f, "  \"global_mpi_rank\": %d,\n", rank);
    fprintf(f, "  \"local_rank\": %d,\n", local_rank);
    fprintf(f, "  \"mpi_world_size\": %d,\n", mpi_size);
    fprintf(f, "  \"SLURM_PROCID\": \""); json_escape(f, getenv("SLURM_PROCID")); fprintf(f, "\",\n");
    fprintf(f, "  \"SLURM_LOCALID\": \""); json_escape(f, getenv("SLURM_LOCALID")); fprintf(f, "\",\n");
    fprintf(f, "  \"CUDA_VISIBLE_DEVICES_ORIGINAL\": \""); json_escape(f, original_cvd); fprintf(f, "\",\n");
    fprintf(f, "  \"CUDA_VISIBLE_DEVICES\": \""); json_escape(f, active_cvd); fprintf(f, "\",\n");
    fprintf(f, "  \"cuda_runtime_visible_device_count\": %d,\n", cuda_count);
    fprintf(f, "  \"selected_cuda_runtime_device_ordinal\": 0,\n");
    fprintf(f, "  \"physical_gpu_pci_bus_id\": \""); json_escape(f, pci_bus_id); fprintf(f, "\",\n");
    fprintf(f, "  \"physical_gpu_uuid\": \""); json_escape(f, uuid); fprintf(f, "\",\n");
    fprintf(f, "  \"timestamp_utc\": \""); json_escape(f, timestamp); fprintf(f, "\",\n");
    fprintf(f, "  \"wrapper_version\": \"qe_rank_wrapper_v1\",\n");
    fprintf(f, "  \"wrapper_source_sha256\": \""); json_escape(f, getenv("HIPAC_WRAPPER_SOURCE_SHA256")); fprintf(f, "\",\n");
    fprintf(f, "  \"validator_sha256\": \""); json_escape(f, getenv("HIPAC_MAPPING_VALIDATOR_SHA256")); fprintf(f, "\",\n");
    fprintf(f, "  \"mpi_route_identity\": \""); json_escape(f, getenv("HIPAC_MPI_ROUTE_IDENTITY")); fprintf(f, "\"\n");
    fprintf(f, "}\n");
    if (fclose(f) != 0) die("cannot close mapping record temp file");
    if (rename(tmp_path, final_path) != 0) die("cannot atomically publish mapping record");
}

static int marker_exists(const char *dir, const char *name) {
    char path[PATH_MAX];
    snprintf(path, sizeof(path), "%s/%s", dir, name);
    return access(path, F_OK) == 0;
}

static void wait_for_global_result(const char *state_dir, int timeout_seconds) {
    time_t deadline = time(NULL) + timeout_seconds;
    while (time(NULL) <= deadline) {
        if (marker_exists(state_dir, "PASS")) return;
        if (marker_exists(state_dir, "FAIL")) exit(51);
        usleep(200000);
    }
    exit(52);
}

static void write_exec_marker(const char *state_dir, int rank) {
    char path[PATH_MAX];
    snprintf(path, sizeof(path), "%s/qe_exec_rank_%d.marker", state_dir, rank);
    FILE *f = fopen(path, "w");
    if (f) {
        fprintf(f, "rank=%d\n", rank);
        fclose(f);
    }
}

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;
    const char *rank_names[] = {"OMPI_COMM_WORLD_RANK", "PMI_RANK", "PMIX_RANK", "SLURM_PROCID", NULL};
    const char *local_names[] = {"OMPI_COMM_WORLD_LOCAL_RANK", "MPI_LOCALRANKID", "SLURM_LOCALID", NULL};
    const char *size_names[] = {"OMPI_COMM_WORLD_SIZE", "PMI_SIZE", "SLURM_NTASKS", NULL};
    int rank = env_int_any(rank_names, -1);
    int local_rank = env_int_any(local_names, -1);
    int mpi_size = env_int_any(size_names, -1);
    if (rank < 0 || local_rank < 0 || mpi_size < 1) die("cannot determine MPI rank/local rank/size");

    const char *records_dir = need_env("HIPAC_MAPPING_RECORDS_DIR");
    const char *state_dir = need_env("HIPAC_MAPPING_STATE_DIR");
    const char *validator = need_env("HIPAC_MAPPING_VALIDATOR");
    const char *qe_bin = need_env("QE_BIN");
    const char *qe_input = need_env("QE_INPUT");
    const char *npools = need_env("HIPAC_QE_NPOOLS");
    int timeout_seconds = atoi(need_env("HIPAC_MAPPING_TIMEOUT_SECONDS"));
    if (timeout_seconds < 1) timeout_seconds = 120;

    const char *original_cvd = getenv("CUDA_VISIBLE_DEVICES");
    char active_cvd[1024];
    choose_cuda_visible_device(local_rank, active_cvd, sizeof(active_cvd));
    setenv("CUDA_VISIBLE_DEVICES", active_cvd, 1);

    int count = -1;
    cudaError_t err = cudaGetDeviceCount(&count);
    if (err != cudaSuccess) {
        fprintf(stderr, "qe_rank_wrapper ERROR: cudaGetDeviceCount: %s\n", cudaGetErrorString(err));
        count = -1;
    }
    char uuid[128] = "";
    char pci_bus_id[128] = "";
    if (count == 1) {
        cudaDeviceProp prop;
        if (cudaSetDevice(0) == cudaSuccess && cudaGetDeviceProperties(&prop, 0) == cudaSuccess) {
            snprintf(uuid, sizeof(uuid), "GPU-%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x",
                (unsigned char)prop.uuid.bytes[0], (unsigned char)prop.uuid.bytes[1],
                (unsigned char)prop.uuid.bytes[2], (unsigned char)prop.uuid.bytes[3],
                (unsigned char)prop.uuid.bytes[4], (unsigned char)prop.uuid.bytes[5],
                (unsigned char)prop.uuid.bytes[6], (unsigned char)prop.uuid.bytes[7],
                (unsigned char)prop.uuid.bytes[8], (unsigned char)prop.uuid.bytes[9],
                (unsigned char)prop.uuid.bytes[10], (unsigned char)prop.uuid.bytes[11],
                (unsigned char)prop.uuid.bytes[12], (unsigned char)prop.uuid.bytes[13],
                (unsigned char)prop.uuid.bytes[14], (unsigned char)prop.uuid.bytes[15]);
            if (cudaDeviceGetPCIBusId(pci_bus_id, sizeof(pci_bus_id), 0) != cudaSuccess) {
                snprintf(pci_bus_id, sizeof(pci_bus_id), "%04x:%02x:%02x.0", prop.pciDomainID, prop.pciBusID, prop.pciDeviceID);
            }
        }
    }

    char host[256];
    if (gethostname(host, sizeof(host)) != 0) snprintf(host, sizeof(host), "unknown");
    host[sizeof(host) - 1] = '\0';
    write_record(records_dir, rank, local_rank, mpi_size, count, uuid, pci_bus_id, host, original_cvd, active_cvd);

    if (rank == 0) {
        char command[8192];
        snprintf(command, sizeof(command),
            "python3 '%s' --records-dir '%s' --result-dir '%s' --summary-path '%s/mapping_summary.json' "
            "--expected-ranks '%s' --expected-nodes '%s' --expected-ranks-per-node '%s' --expected-gpus-per-node '%s' --timeout-seconds '%s' > '%s/mapping_validator.log' 2>&1",
            validator, records_dir, state_dir, need_env("RUN_DIR"),
            need_env("HIPAC_EXPECTED_RANKS"), need_env("HIPAC_EXPECTED_NODES"),
            need_env("HIPAC_EXPECTED_RANKS_PER_NODE"), need_env("HIPAC_EXPECTED_GPUS_PER_NODE"),
            need_env("HIPAC_MAPPING_TIMEOUT_SECONDS"), need_env("RUN_DIR"));
        (void)system(command);
    }

    wait_for_global_result(state_dir, timeout_seconds + 5);
    write_exec_marker(state_dir, rank);

    const char *extra = getenv("HIPAC_QE_EXTRA_ARGS");
    char *exec_args[128];
    int n = 0;
    exec_args[n++] = (char *)qe_bin;
    exec_args[n++] = (char *)"-nk";
    exec_args[n++] = (char *)npools;
    if (extra != NULL && extra[0] != '\0') {
        char *copy = strdup(extra);
        char *save = NULL;
        for (char *tok = strtok_r(copy, " ", &save); tok != NULL && n < 124; tok = strtok_r(NULL, " ", &save)) {
            exec_args[n++] = tok;
        }
    }
    exec_args[n++] = (char *)"-in";
    exec_args[n++] = (char *)qe_input;
    exec_args[n] = NULL;
    execv(qe_bin, exec_args);
    perror("execv pw.x");
    return 60;
}
