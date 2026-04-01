from __future__ import annotations

import csv
import pickle
import sqlite3
import zipfile
from pathlib import Path

from dataset_registry.catalog import inspect_source


def test_inspect_wesad_source_passes_with_minimal_valid_fixture(tmp_path: Path) -> None:
    subject_dir = tmp_path / "S2"
    e4_dir = subject_dir / "S2_E4_Data"
    subject_dir.mkdir(parents=True)
    e4_dir.mkdir()

    (subject_dir / "S2_quest.csv").write_text("# Subj;S2;;;;\n", encoding="utf-8")
    (subject_dir / "S2_respiban.txt").write_text("respiban\n", encoding="utf-8")
    (subject_dir / "S2_readme.txt").write_text("readme\n", encoding="utf-8")

    payload = {
        "subject": "S2",
        "label": [1, 2, 3],
        "signal": {
            "chest": {
                "ACC": [[1, 2, 3], [1, 2, 3], [1, 2, 3]],
                "ECG": [[1], [1], [1]],
                "EMG": [[1], [1], [1]],
                "EDA": [[1], [1], [1]],
                "Temp": [[1], [1], [1]],
                "Resp": [[1], [1], [1]],
            },
            "wrist": {
                "ACC": [[1, 2, 3]],
                "BVP": [[1]],
                "EDA": [[1]],
                "TEMP": [[1]],
            },
        },
    }
    with (subject_dir / "S2.pkl").open("wb") as handle:
        pickle.dump(payload, handle)

    result = inspect_source("wesad", tmp_path)
    assert result.status == "passed"


def test_inspect_wesad_accepts_colon_variant_in_quest_header(tmp_path: Path) -> None:
    subject_dir = tmp_path / "S3"
    e4_dir = subject_dir / "S3_E4_Data"
    subject_dir.mkdir(parents=True)
    e4_dir.mkdir()

    (subject_dir / "S3_quest.csv").write_text("# Subj:;S3;;;;\n", encoding="utf-8")
    (subject_dir / "S3_respiban.txt").write_text("respiban\n", encoding="utf-8")
    (subject_dir / "S3_readme.txt").write_text("readme\n", encoding="utf-8")

    payload = {
        "subject": "S3",
        "label": [1, 1, 1],
        "signal": {
            "chest": {
                "ACC": [[1, 2, 3], [1, 2, 3], [1, 2, 3]],
                "ECG": [[1], [1], [1]],
                "EMG": [[1], [1], [1]],
                "EDA": [[1], [1], [1]],
                "Temp": [[1], [1], [1]],
                "Resp": [[1], [1], [1]],
            },
            "wrist": {
                "ACC": [[1, 2, 3]],
                "BVP": [[1]],
                "EDA": [[1]],
                "TEMP": [[1]],
            },
        },
    }
    with (subject_dir / "S3.pkl").open("wb") as handle:
        pickle.dump(payload, handle)

    result = inspect_source("wesad", tmp_path)
    assert result.status == "passed"


def test_inspect_emowear_source_passes_with_minimal_valid_fixture(tmp_path: Path) -> None:
    participant_dir = tmp_path / "01-9TZK"
    participant_dir.mkdir(parents=True)

    with (tmp_path / "meta.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Code",
                "ID",
                "Sequence",
                "Experiment",
                "Empatica E4",
                "Zephyr BioHarness 3",
                "Front STb",
                "Back STb",
                "Water STb",
                "Notes",
            ]
        )
        writer.writerow(["1", "9TZK", "0", "VAD", "", "", "", "", "", ""])

    with (tmp_path / "questionnaire.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Code",
                "ID",
                "Age",
                "Gender",
                "Handedness",
                "Vision",
                "Vision aid",
                "Education",
                "Alcohol consumption",
                "Coffee consumption",
                "Tea consumption",
                "Tobacco consumption",
                "Other drug/medication consumption",
                "Normal hours of sleep",
                "Hours of sleep last night",
                "Level of Alertness",
                "Physical/psychiatric syndroms",
            ]
        )
        writer.writerow(["1", "9TZK", "26", "Male", "left", "acceptable", "none", "master", "never", "never", "never", "never", "never", "8", "7", "high", ""])

    with sqlite3.connect(str(tmp_path / "mqtt.db")) as connection:
        connection.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")

    with zipfile.ZipFile(participant_dir / "e4.zip", "w") as archive:
        archive.writestr("ACC.csv", "1,1,1\n32,32,32\n24,53,27\n")
        archive.writestr("BVP.csv", "1\n64\n0.1\n")
        archive.writestr("EDA.csv", "1\n4\n0.1\n")
        archive.writestr("HR.csv", "1\n1\n60\n")
        archive.writestr("IBI.csv", "1,IBI\n0.5,0.7\n")
        archive.writestr("TEMP.csv", "1\n4\n30\n")
        archive.writestr("info.txt", "info\n")
        archive.writestr("tags.csv", "1\n")

    with zipfile.ZipFile(participant_dir / "bh3.zip", "w") as archive:
        archive.writestr("log_test_Accel.csv", "Time,AccelX\n03/05/2022 10:30:30.426,1\n")
        archive.writestr("log_test_BB.csv", "Time,BB\n03/05/2022 10:30:30.426,1\n")
        archive.writestr("log_test_Breathing.csv", "Time,BreathingWaveform\n03/05/2022 10:30:30.426,1\n")
        archive.writestr("log_test_ECG.csv", "Time,EcgWaveform\n03/05/2022 10:30:30.426,3916\n")
        archive.writestr("log_test_Event_Data.csv", "SeqNo, Year, Month\n0,2022,05\n")
        archive.writestr("log_test_GPS.csv", "Time,Lat\n03/05/2022 10:30:30.426,1\n")
        archive.writestr("log_test_RR.csv", "Time,RR\n03/05/2022 10:30:30.426,1\n")
        archive.writestr("log_test_SessionInfo.txt", "session\n")
        archive.writestr("log_test_SummaryEnhanced.csv", "Time,Summary\n03/05/2022 10:30:30.426,1\n")
        archive.writestr("info.txt", "info\n")

    result = inspect_source("emowear", tmp_path)
    assert result.status == "passed"


def test_inspect_dapper_source_passes_with_minimal_valid_fixture(tmp_path: Path) -> None:
    participant_dir = tmp_path / "1001"
    participant_dir.mkdir(parents=True)
    (tmp_path / "README.txt").write_text("readme\n", encoding="utf-8")

    (participant_dir / "20200101_20200102.csv").write_text(
        "heart_rate,motion,GSR,battery_info,time\n67.3,9.8,0.006,100,2019/11/24 9:24:57\n",
        encoding="utf-8",
    )
    (participant_dir / "20200101_20200102_ACC.csv").write_text(
        "Motion_dataX,Motion_dataY,Motion_dataZ,csv_time_motion\n-2.9,-6.9,6.5,2019-11-24 09:24:57\n",
        encoding="utf-8",
    )
    (participant_dir / "20200101_20200102_GSR.csv").write_text(
        "GSR,csv_time_GSR\n0.006,2019-11-24 09:24:57\n",
        encoding="utf-8",
    )
    (participant_dir / "20200101_20200102_PPG.csv").write_text(
        "PPG,csv_time_PPG\n0.047,2019-11-24 09:24:57\n",
        encoding="utf-8",
    )

    result = inspect_source("dapper", tmp_path)
    assert result.status == "passed"


def test_inspect_dapper_reports_zero_byte_sensor_file_as_warning(tmp_path: Path) -> None:
    participant_dir = tmp_path / "1001"
    participant_dir.mkdir(parents=True)
    (tmp_path / "README.txt").write_text("readme\n", encoding="utf-8")

    (participant_dir / "20200101_20200102.csv").write_text(
        "heart_rate,motion,GSR,battery_info,time\n67.3,9.8,0.006,100,2019/11/24 9:24:57\n",
        encoding="utf-8",
    )
    (participant_dir / "20200101_20200102_ACC.csv").write_text(
        "Motion_dataX,Motion_dataY,Motion_dataZ,csv_time_motion\n-2.9,-6.9,6.5,2019-11-24 09:24:57\n",
        encoding="utf-8",
    )
    (participant_dir / "20200101_20200102_GSR.csv").write_text("", encoding="utf-8")
    (participant_dir / "20200101_20200102_PPG.csv").write_text(
        "PPG,csv_time_PPG\n0.047,2019-11-24 09:24:57\n",
        encoding="utf-8",
    )

    result = inspect_source("dapper", tmp_path)

    assert result.status == "warning"
    zero_byte_check = next(check for check in result.checks if check["description"] == "No zero-byte DAPPER sensor files are present.")
    assert zero_byte_check["status"] == "warning"
    assert zero_byte_check["details"] == {"empty_file_count": 1}


def test_inspect_grex_source_passes_with_minimal_valid_fixture(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# cinemaDataset\n", encoding="utf-8")

    for rel in [
        "1_Stimuli/Raw",
        "1_Stimuli/Transformed",
        "2_Questionnaire/Raw",
        "2_Questionnaire/Transformed",
        "3_Physio/Raw",
        "3_Physio/Transformed",
        "4_Annotation/Transformed",
        "5_Scripts",
        "6_Results/EDA",
        "6_Results/PPG",
        "6_Results/Analysis",
    ]:
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)

    with (tmp_path / "1_Stimuli/Raw/video_info.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["", "movie_ID", "movie_name", "duration", "bit_rate", "fps", "encoding", "video_resolution_width", "video_resolution_height", "genre"])
        writer.writerow(["0", "m0", "Clip", "00:00:10.00", "1000", "24", "h264", "1280", "720", "Drama"])
    (tmp_path / "1_Stimuli/Raw/video_info.json").write_text(
        '[{"movie_ID":"m0","movie_name":"Clip","duration":"00:00:10.00","bit_rate":"1000","fps":"24","encoding":"h264","video_resolution_width":"1280","video_resolution_height":"720","genre":"Drama"}]\n',
        encoding="utf-8",
    )

    with (tmp_path / "2_Questionnaire/Raw/quest_raw_data.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["", "ID", "movie", "device", "session", "age", "gender", "friends", "pre-viewing", "pos-viewing", "personality"])
        writer.writerow(["0", "0", "Clip", "34", "0", "18-29", "M", "", "[2, 3]", "[2, 3]", "[0.1, 0.2]"])
    (tmp_path / "2_Questionnaire/Raw/quest_raw_data.json").write_text(
        '[{"ID":"0","movie":"Clip","device":"34","session":"0","age":"18-29","gender":"M","friends":"","pre-viewing":"[2, 3]","pos-viewing":"[2, 3]","personality":"[0.1, 0.2]"}]\n',
        encoding="utf-8",
    )

    payloads = {
        "1_Stimuli/Transformed/stimu_trans_data_session.pickle": {"genre": ["Drama"], "movie": ["Clip"], "session": [0]},
        "1_Stimuli/Transformed/stimu_trans_data_segments.pickle": {"genre": ["Drama", "Drama"], "movie": ["Clip", "Clip"], "session": [0, 0]},
        "2_Questionnaire/Transformed/quest_trans_data_session.pickle": {"ID": [0], "device": [34]},
        "2_Questionnaire/Transformed/quest_trans_data_segments.pickle": {"ID": [0, 0], "device": [34, 34]},
        "3_Physio/Transformed/physio_trans_data_session.pickle": {
            "filt_EDA": [[1.0]],
            "filt_PPG": [[2.0]],
            "ts": [[0.0]],
            "sampling_rate": [4],
            "packet_number": [[1]],
            "EDR": [[0.1]],
            "hr": [[70.0]],
            "raw_EDA": [[1.0]],
            "raw_PPG": [[2.0]],
            "hr_idx": [[0]],
            "EDA_quality_idx": [0],
            "PPG_quality_idx": [0],
        },
        "3_Physio/Transformed/physio_trans_data_segments.pickle": {
            "filt_EDA": [[1.0], [1.1]],
            "filt_PPG": [[2.0], [2.1]],
            "ts": [[0.0], [0.0]],
            "sampling_rate": [4, 4],
            "packet_number": [[1], [2]],
            "EDR": [[0.1], [0.2]],
            "hr": [[70.0], [71.0]],
            "raw_EDA": [[1.0], [1.1]],
            "raw_PPG": [[2.0], [2.1]],
            "hr_idx": [[0], [0]],
            "EDA_quality_idx": [0],
            "PPG_quality_idx": [0],
        },
        "4_Annotation/Transformed/ann_trans_data_segments.pickle": {
            "ar_seg": [1, 2],
            "ts_seg": [0.0, 1.0],
            "unc_seg": [None, None],
            "vl_seg": [3, 4],
        },
    }
    for rel, payload in payloads.items():
        with (tmp_path / rel).open("wb") as handle:
            pickle.dump(payload, handle)

    (tmp_path / "3_Physio/Raw/S0_physio_raw_data_M0.hdf5").write_bytes(
        b"\x89HDF\r\n\x1a\n" + b"data Arousal EDA Valence EDA sampling rate movie"
    )

    result = inspect_source("grex", tmp_path)
    assert result.status == "passed"
