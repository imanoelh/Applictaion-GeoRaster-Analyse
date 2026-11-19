import { useMemo, useState } from "react";
import { CalendarDays } from "lucide-react";
import { arSA, enGB } from "date-fns/locale";

import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { Language } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type LocalizedDatePickerProps = {
  value: string;
  onChange: (value: string) => void;
  language: Language;
  className?: string;
};

function parseIsoDate(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return undefined;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.getTime()) ? undefined : date;
}

function toIsoDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function LocalizedDatePicker({
  value,
  onChange,
  language,
  className,
}: LocalizedDatePickerProps) {
  const [open, setOpen] = useState(false);
  const isArabic = language === "ar";
  const selected = useMemo(() => parseIsoDate(value), [value]);
  const formattedValue = selected
    ? new Intl.DateTimeFormat(isArabic ? "ar-SA-u-ca-gregory" : "en-GB", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      }).format(selected)
    : isArabic
      ? "اختر التاريخ"
      : "Select date";

  const selectDate = (date: Date | undefined) => {
    if (!date) return;
    onChange(toIsoDate(date));
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          lang={isArabic ? "ar-SA" : "en-GB"}
          dir={isArabic ? "rtl" : "ltr"}
          aria-label={isArabic ? "اختيار التاريخ" : "Select date"}
          className={cn(
            "flex h-8 w-full items-center justify-between gap-2 rounded-md border bg-card px-2 py-1.5 text-xs text-foreground",
            className,
          )}
        >
          <span className="tabular-nums">{formattedValue}</span>
          <CalendarDays className="size-3.5 shrink-0" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="z-[1200] w-auto p-0"
        lang={isArabic ? "ar-SA" : "en-GB"}
        dir={isArabic ? "rtl" : "ltr"}
      >
        <Calendar
          mode="single"
          selected={selected}
          onSelect={selectDate}
          defaultMonth={selected}
          locale={isArabic ? arSA : enGB}
          dir={isArabic ? "rtl" : "ltr"}
        />
        <div className="flex items-center justify-between border-t px-3 py-2 text-xs">
          <button
            type="button"
            className="font-medium text-primary hover:underline"
            onClick={() => {
              onChange("");
              setOpen(false);
            }}
          >
            {isArabic ? "مسح" : "Clear"}
          </button>
          <button
            type="button"
            className="font-medium text-primary hover:underline"
            onClick={() => selectDate(new Date())}
          >
            {isArabic ? "اليوم" : "Today"}
          </button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
