import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import IrrigationPanel from "./IrrigationPanel";
import { irrigationRequest } from "./api";
vi.mock("./api", () => ({ irrigationRequest: vi.fn() }));
afterEach(() => vi.resetAllMocks());
const policy = { crop: "Cây thử", stage: "Giả lập", substrate: "Giả lập", moisture_stop_pct: 80, max_pulse_seconds: 2, cooldown_seconds: 300, daily_budget_seconds: 10, evaluation_seconds: 60 };
it("requires explicit configuration and submits AUTO policy", async () => {
  vi.mocked(irrigationRequest).mockResolvedValue({ execution_scope: 'simulator_only', profile: { enabled: false, policy, last_status: 'configured' }, decisions: [] });
  render(<IrrigationPanel deviceId="node_01" />);
  await screen.findByDisplayValue("Cây thử");
  fireEvent.click(screen.getByRole('button', { name: 'Bật AUTO (simulator)' }));
  await waitFor(() => expect(irrigationRequest).toHaveBeenCalledWith('node_01', { enabled: true, policy: { ...policy, force_water_below_pct: null } }));
});
it("uses the acknowledged profile when disarming, and shows command evidence", async () => {
  vi.mocked(irrigationRequest).mockResolvedValue({ execution_scope: 'simulator_only', profile: { enabled: true, policy, last_status: 'sent' }, decisions: [{ id: '1', status: 'sent', reason: 'Thử nghiệm', created_at: new Date().toISOString(), proposal: null, command_id: 'cmd1', command_status: 'pending', confirmed_relay_state: null }] });
  render(<IrrigationPanel deviceId="node_01" />);
  await screen.findByText('AUTO đang bật');
  expect(screen.getByText(/Relay xác nhận: Chưa có/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Chuyển MANUAL và gửi STOP' }));
  await waitFor(() => expect(irrigationRequest).toHaveBeenCalledWith('node_01', { enabled: false, policy }));
});

it("requires explicit confirmation before arming the physical ESP32", async () => {
  vi.mocked(irrigationRequest).mockResolvedValue({ execution_scope: 'real_device', profile: { enabled: false, policy, last_status: 'configured' }, decisions: [] });
  render(<IrrigationPanel deviceId="node_01" />);
  const arm = await screen.findByRole('button', { name: 'Bật AUTO (ESP32 thật)' });
  expect(arm).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox', { name: /Đã hiệu chuẩn cảm biến/ }));
  expect(arm).toBeEnabled();
  fireEvent.click(arm);
  await waitFor(() => expect(irrigationRequest).toHaveBeenCalledWith('node_01', { enabled: true, policy: { ...policy, force_water_below_pct: null } }));
});

it("does not arm when the server has not confirmed an execution scope", async () => {
  vi.mocked(irrigationRequest).mockResolvedValue({ profile: { enabled: false, policy, last_status: 'configured' }, decisions: [] });
  render(<IrrigationPanel deviceId="node_01" />);
  await screen.findByDisplayValue("Cây thử");
  expect(screen.getByRole('button', { name: 'Bật AUTO' })).toBeDisabled();
});

it("resets real-device confirmation when switching devices", async () => {
  vi.mocked(irrigationRequest).mockResolvedValue({ execution_scope: 'real_device', profile: { enabled: false, policy, last_status: 'configured' }, decisions: [] });
  const { rerender } = render(<IrrigationPanel deviceId="node_01" />);
  await screen.findByRole('button', { name: 'Bật AUTO (ESP32 thật)' });
  fireEvent.click(screen.getByRole('checkbox'));
  expect(screen.getByRole('button', { name: 'Bật AUTO (ESP32 thật)' })).toBeEnabled();
  rerender(<IrrigationPanel deviceId="node_02" />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Bật AUTO (ESP32 thật)' })).toBeDisabled());
  expect(screen.getByRole('checkbox')).not.toBeChecked();
});

it("can disarm a real ESP32 without an arming confirmation", async () => {
  vi.mocked(irrigationRequest).mockResolvedValue({ execution_scope: 'real_device', profile: { enabled: true, policy, last_status: 'sent' }, decisions: [] });
  render(<IrrigationPanel deviceId="node_01" />);
  await screen.findByText('AUTO đang bật');
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Chuyển MANUAL và gửi STOP' }));
  await waitFor(() => expect(irrigationRequest).toHaveBeenCalledWith('node_01', { enabled: false, policy }));
});

it("keeps AUTO locked if the profile request fails", async () => {
  vi.mocked(irrigationRequest).mockRejectedValue(new Error('offline'));
  render(<IrrigationPanel deviceId="node_01" />);
  await screen.findByRole('status');
  expect(screen.getByRole('button', { name: 'Bật AUTO' })).toBeDisabled();
});

it("submits the optional threshold rule and labels rule decisions apart from AI", async () => {
  const decisions = [
    { id: '1', status: 'sent', reason: 'Luật ngưỡng: độ ẩm đất 30% < 33%', created_at: new Date().toISOString(), decision_source: 'rule', proposal: { water: true, duration_seconds: 10, reason: 'Luật ngưỡng: độ ẩm đất 30% < 33%' }, command_id: 'cmd1', command_status: 'applied', confirmed_relay_state: 'on' },
    { id: '2', status: 'no_water', reason: 'Chờ thêm', created_at: new Date().toISOString(), decision_source: 'ai', proposal: { water: false, duration_seconds: 0, reason: 'Chờ thêm' }, command_id: null, command_status: null, confirmed_relay_state: null },
  ];
  vi.mocked(irrigationRequest).mockResolvedValue({ execution_scope: 'simulator_only', profile: { enabled: false, policy, last_status: 'configured' }, decisions });
  render(<IrrigationPanel deviceId="node_01" />);
  await screen.findByDisplayValue("Cây thử");
  expect(screen.getByText(/Luật ngưỡng: Đề xuất tưới 10s/)).toBeInTheDocument();
  expect(screen.getByText(/AI: Không tưới — Chờ thêm/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/Luật ngưỡng: tưới 10 giây/), { target: { value: '33' } });
  fireEvent.click(screen.getByRole('button', { name: 'Bật AUTO (simulator)' }));
  await waitFor(() => expect(irrigationRequest).toHaveBeenCalledWith('node_01', { enabled: true, policy: { ...policy, force_water_below_pct: 33 } }));
});
