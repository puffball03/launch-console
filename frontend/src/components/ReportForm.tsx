import { FormEvent, ReactNode, useState } from "react";

import { FieldErrors, fileReport, ReportInput, Station, STATIONS } from "../api";

type Props = {
  onFiled: (id: number) => void;
};

const NOTE_MAX_CHARS = 2000;

const EMPTY = {
  engineer_name: "",
  station: "",
  wind_knots: "",
  temp_c: "",
  fuel_pct: "",
  note: "",
};

type Values = typeof EMPTY;
type Field = keyof Values;

const LABELS: Record<Field, string> = {
  engineer_name: "Name",
  station: "Station",
  wind_knots: "Wind",
  temp_c: "Temperature",
  fuel_pct: "Fuel",
  note: "Note",
};

/** Mirrors the server's rules and messages so most mistakes are caught before sending. */
function validate(values: Values): FieldErrors {
  const errors: FieldErrors = {};
  for (const field of ["engineer_name", "station", "note"] as const) {
    if (!values[field].trim()) errors[field] = `${LABELS[field]} is required.`;
  }
  if (!errors.note && values.note.trim().length > NOTE_MAX_CHARS) {
    errors.note = `Note must be ${NOTE_MAX_CHARS} characters or fewer.`;
  }
  for (const field of ["wind_knots", "temp_c", "fuel_pct"] as const) {
    const raw = values[field].trim();
    const value = Number(raw);
    if (raw === "") errors[field] = `${LABELS[field]} is required.`;
    else if (!Number.isFinite(value)) errors[field] = `${LABELS[field]} must be a number.`;
    else if (field !== "temp_c" && value < 0) errors[field] = `${LABELS[field]} cannot be negative.`;
  }
  return errors;
}

function toInput(values: Values): ReportInput {
  return {
    engineer_name: values.engineer_name.trim(),
    station: values.station as Station,
    wind_knots: Number(values.wind_knots),
    temp_c: Number(values.temp_c),
    fuel_pct: Number(values.fuel_pct),
    note: values.note.trim(),
  };
}

export default function ReportForm({ onFiled }: Props) {
  const [values, setValues] = useState<Values>(EMPTY);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [sending, setSending] = useState(false);

  function set(field: Field) {
    return (event: { target: { value: string } }) => {
      setValues((v) => ({ ...v, [field]: event.target.value }));
      setErrors((e) => ({ ...e, [field]: undefined }));
    };
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const found = validate(values);
    setErrors(found);
    if (Object.values(found).some(Boolean)) return;

    setSending(true);
    let result;
    try {
      result = await fileReport(toInput(values));
    } catch {
      setErrors({ _body: "Could not reach the server. Check the connection and try again." });
      return;
    } finally {
      setSending(false);
    }
    if (result.ok) {
      setValues(EMPTY);
      onFiled(result.id);
    } else {
      setErrors(result.errors);
    }
  }

  function field(name: Field, label: string, control: ReactNode) {
    return (
      <div className="field">
        <label htmlFor={name}>{label}</label>
        {control}
        {errors[name] && (
          <p id={`${name}-error`} className="field-error">
            {errors[name]}
          </p>
        )}
      </div>
    );
  }

  function aria(name: Field) {
    return errors[name]
      ? { "aria-invalid": true, "aria-describedby": `${name}-error` }
      : {};
  }

  return (
    <form className="report-form" onSubmit={submit} noValidate>
      {field(
        "engineer_name",
        "Name",
        <input id="engineer_name" value={values.engineer_name} onChange={set("engineer_name")} {...aria("engineer_name")} />,
      )}
      {field(
        "station",
        "Station",
        <select id="station" value={values.station} onChange={set("station")} {...aria("station")}>
          <option value="">Select…</option>
          {STATIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>,
      )}
      {field(
        "wind_knots",
        "Wind (knots)",
        <input id="wind_knots" type="number" step="any" value={values.wind_knots} onChange={set("wind_knots")} {...aria("wind_knots")} />,
      )}
      {field(
        "temp_c",
        "Temperature (°C)",
        <input id="temp_c" type="number" step="any" value={values.temp_c} onChange={set("temp_c")} {...aria("temp_c")} />,
      )}
      {field(
        "fuel_pct",
        "Fuel (%)",
        <input id="fuel_pct" type="number" step="any" value={values.fuel_pct} onChange={set("fuel_pct")} {...aria("fuel_pct")} />,
      )}
      {field(
        "note",
        "Note",
        <textarea id="note" rows={4} value={values.note} onChange={set("note")} {...aria("note")} />,
      )}
      {errors._body && (
        <p role="alert" className="form-error">
          {errors._body}
        </p>
      )}
      <button type="submit" disabled={sending}>
        File report
      </button>
    </form>
  );
}
