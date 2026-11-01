import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import IrrigationPanel from "./IrrigationPanel";
import { irrigationRequest } from "./api";
vi.mock("./api", () => ({ irrigationRequest: vi.fn() }));
afterEach(() => vi.resetAllMocks());
const policy = { crop: "Cây thử", stage: "Giả lập", substrate: "Giả lập", moisture_stop_pct: 80, max_pulse_seconds: 2, cooldown_seconds: 300, daily_budget_seconds: 10, evaluation_seconds: 60 };
it("requires explicit configuration and submits AUTO policy", async () => {
  vi.mocked(irrigationRequest).mockResolvedValue({ profile: { enabled: false, policy, last_status: 'configured' }, decisions: [] });
  render(<IrrigationPanel deviceId="node_01" />);
  await screen.findByDisplayValue("Cây thử");
  fireEvent.click(screen.getByRole('button', { name: 'Bật AUTO (simulator)' }));
  await waitFor(() => expect(irrigationRequest).toHaveBeenCalledWith('node_01', { enabled: true, policy }));
});
it("uses the acknowledged profile when disarming, and shows command evidence", async () => {
  vi.mocked(irrigationRequest).mockResolvedValue({ profile: { enabled: true, policy, last_status: 'sent' }, decisions: [{ id: '1', status: 'sent', reason: 'Thử nghiệm', created_at: new Date().toISOString(), proposal: null, command_id: 'cmd1', command_status: 'pending', confirmed_relay_state: null }] });
  render(<IrrigationPanel deviceId="node_01" />);
  await screen.findByText('AUTO đang bật');
  expect(screen.getByText(/Relay xác nhận: Chưa có/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Chuyển MANUAL và gửi STOP' }));
  await waitFor(() => expect(irrigationRequest).toHaveBeenCalledWith('node_01', { enabled: false, policy }));
});
