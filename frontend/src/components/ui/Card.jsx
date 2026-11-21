import { cx } from "../../utils/cx.js";

export function Card({ as: Tag = "section", className, children, ...props }) {
  return <Tag className={cx("card", className)} {...props}>{children}</Tag>;
}
