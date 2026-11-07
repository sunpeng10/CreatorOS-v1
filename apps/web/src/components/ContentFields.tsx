"use client";
import { useId, useRef, useState } from "react";
import { CalendarDays } from "lucide-react";

export function EditableChoice({
  name,
  options,
  value,
  onChange,
}: {
  name: string;
  options: readonly string[];
  value?: string;
  onChange?: (value: string) => void;
}) {
  const id = useId();
  return (
    <>
      <input
        name={name}
        list={id}
        value={value}
        onChange={
          onChange ? (event) => onChange(event.target.value) : undefined
        }
        autoComplete="off"
      />
      <datalist id={id}>
        {options.map((option) => (
          <option key={option} value={option} />
        ))}
      </datalist>
    </>
  );
}

function parseDate(value: string) {
  const match = value
    .trim()
    .match(/^(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})日?$/);
  if (!match) return "";
  const iso = `${match[1]}-${match[2].padStart(2, "0")}-${match[3].padStart(2, "0")}`;
  const date = new Date(`${iso}T00:00:00Z`);
  return Number.isFinite(date.valueOf()) &&
    date.toISOString().slice(0, 10) === iso
    ? iso
    : "";
}
function dateText(iso: string) {
  return iso
    ? `${iso.slice(0, 4)}年${iso.slice(5, 7)}月${iso.slice(8, 10)}日`
    : "";
}
export function ChineseDateInput() {
  const picker = useRef<HTMLInputElement>(null);
  const textInput = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState("");
  const [iso, setIso] = useState("");
  return (
    <div className="chinese-date">
      <input
        ref={textInput}
        value={value}
        placeholder="YYYY年MM月DD日"
        inputMode="text"
        onChange={(event) => {
          const text = event.target.value;
          const parsed = parseDate(text);
          setValue(text);
          setIso(parsed);
          event.target.setCustomValidity(
            text.trim() && !parsed ? "请填写有效的年、月、日。" : "",
          );
        }}
        onBlur={() => {
          if (iso) setValue(dateText(iso));
        }}
      />
      <input
        ref={picker}
        className="native-date"
        type="date"
        name="published_at"
        value={iso}
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          setIso(event.target.value);
          setValue(dateText(event.target.value));
          textInput.current?.setCustomValidity("");
        }}
      />
      <button
        type="button"
        className="date-picker-button"
        aria-label="打开发布日期日历"
        onClick={() => {
          if (picker.current?.showPicker) picker.current.showPicker();
          else picker.current?.click();
        }}
      >
        <CalendarDays size={18} />
      </button>
    </div>
  );
}
