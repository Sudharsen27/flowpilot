import type { ComponentProps, ReactNode } from "react";

import { Label } from "@/components/forms/label";
import { cn } from "@/lib/utils";

type FormFieldProps = ComponentProps<"div"> & {
  label: ReactNode;
  htmlFor: string;
  description?: ReactNode;
  error?: ReactNode;
  required?: boolean;
};

export function FormField({
  label,
  htmlFor,
  description,
  error,
  required,
  className,
  children,
  ...props
}: FormFieldProps) {
  return (
    <div className={cn("grid gap-1.5", className)} {...props}>
      <Label htmlFor={htmlFor}>
        {label}
        {required ? (
          <>
            <span aria-hidden="true"> *</span>
            <span className="sr-only"> (required)</span>
          </>
        ) : null}
      </Label>
      {children}
      {error ? (
        <p
          id={`${htmlFor}-error`}
          className="text-danger-text text-xs"
          role="alert"
        >
          {error}
        </p>
      ) : description ? (
        <p
          id={`${htmlFor}-description`}
          className="text-muted-foreground text-xs leading-5"
        >
          {description}
        </p>
      ) : null}
    </div>
  );
}
