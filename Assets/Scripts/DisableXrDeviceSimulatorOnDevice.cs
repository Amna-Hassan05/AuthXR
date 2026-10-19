using UnityEngine;
using UnityEngine.InputSystem;

/// <summary>
/// XR Device Simulator (and SimulatedDeviceLifecycleManager) run very early and
/// can remove the real OpenXR HMD/controllers on Quest. This must run first.
/// Editor Play Mode is left unchanged so laptop testing still works.
/// </summary>
[DefaultExecutionOrder(-32768)]
public class DisableXrDeviceSimulatorOnDevice : MonoBehaviour
{
    void Awake()
    {
        if (Application.isEditor)
            return;

        StripSimulator(gameObject);
    }

    public static void StripAllInScene()
    {
        if (Application.isEditor)
            return;

        var behaviours = FindObjectsByType<MonoBehaviour>(FindObjectsInactive.Include);
        for (int i = 0; i < behaviours.Length; i++)
        {
            var mb = behaviours[i];
            if (mb == null)
                continue;
            if (!IsSimulatorType(mb.GetType().Name))
                continue;
            StripSimulator(mb.gameObject);
        }

        RemoveSimulatedInputDevices();
    }

    static void StripSimulator(GameObject go)
    {
        if (go == null)
            return;

        var behaviours = go.GetComponents<MonoBehaviour>();
        for (int i = 0; i < behaviours.Length; i++)
        {
            var mb = behaviours[i];
            if (mb == null || mb is DisableXrDeviceSimulatorOnDevice)
                continue;
            if (!IsSimulatorType(mb.GetType().Name))
                continue;
            mb.enabled = false;
            DestroyImmediate(mb);
        }

        go.SetActive(false);
    }

    static bool IsSimulatorType(string typeName)
    {
        return typeName == "XRDeviceSimulator" ||
               typeName.StartsWith("XRDeviceSimulator") ||
               typeName == "XRInteractionSimulator" ||
               typeName == "SimulatedDeviceLifecycleManager" ||
               typeName == "XRDeviceSimulatorHandsProvider";
    }

    public static void RemoveSimulatedInputDevices()
    {
        if (Application.isEditor)
            return;

        for (int i = InputSystem.devices.Count - 1; i >= 0; i--)
        {
            var device = InputSystem.devices[i];
            if (device == null)
                continue;

            string typeName = device.GetType().Name;
            if (typeName.IndexOf("Simulated") >= 0)
                InputSystem.RemoveDevice(device);
        }
    }
}
