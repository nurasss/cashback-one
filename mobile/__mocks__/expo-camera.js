// Manual mock for expo-camera used by Jest. For node_modules packages a root __mocks__ file
// is applied automatically, so every suite (including ones that only import CardScanner
// transitively) gets the fake CameraView instead of native code.
const React = require('react');
const { View } = require('react-native');

// Tests flip these flags before rendering; the fake hook keeps React state per mounted scanner.
const state = {
  initialGranted: false,
  nextGranted: false,
  handler: null,
  barcodeTypes: null,
  holdRequest: false,
};

const CameraView = props => {
  state.handler = props.onBarcodeScanned || null;
  state.barcodeTypes = (props.barcodeScannerSettings && props.barcodeScannerSettings.barcodeTypes) || null;
  return React.createElement(View, { testID: 'camera-view' });
};

const PermissionStatus = { GRANTED: 'granted', UNDETERMINED: 'undetermined', DENIED: 'denied' };

// Before the first request the status is "undetermined", as on a real device.
// state.holdRequest keeps the system dialog "open" so tests can check that moment.
const useCameraPermissions = () => {
  const [status, setStatus] = React.useState(state.initialGranted ? 'granted' : 'undetermined');
  const request = React.useCallback(async () => {
    if (state.holdRequest) return { granted: false, canAskAgain: true, status: 'undetermined' };
    const next = state.nextGranted ? 'granted' : 'denied';
    setStatus(next);
    return { granted: state.nextGranted, canAskAgain: true, status: next };
  }, []);
  return [{ granted: status === 'granted', canAskAgain: true, status }, request];
};

module.exports = { __cameraState: state, CameraView, PermissionStatus, useCameraPermissions };
