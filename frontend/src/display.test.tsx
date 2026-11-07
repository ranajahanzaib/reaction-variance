import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { pct } from "./display";
describe("scientific value display", () => {
  it("distinguishes measured zero and unavailable", () => {
    render(
      <table>
        <tbody>
          <tr>
            <td>{pct(0)}</td>
            <td>{pct(null)}</td>
          </tr>
        </tbody>
      </table>,
    );
    expect(screen.getByText("0.0%")).toBeDefined();
    expect(screen.getByText("Unavailable")).toBeDefined();
  });
  it("preserves percentage scale and never clips", () => {
    expect(pct(50)).toBe("50.0%");
    expect(pct(147.37291)).toBe("147.4%");
  });
});
