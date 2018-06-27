import hifiberrydsp.filtering.biquad as biquad
import hifiberrydsp.hardware.adau145x as adau
import hifiberrydsp.hardware.sigmatcp as sigmatcp
import hifiberrydsp.dsptoolkit as dsptoolkit


def demo_sigmatcp():
    dsp = adau.Adau145x()
    st = sigmatcp.SigmaTCP(dsp, "192.168.4.184")
    st.connect()
    print("Writing volume to DSP")
    st.write_decimal(0xb9, 0.05)
    st.write_memory(0xbd, ba)
    st.write_decibel(0xb9, -25)
    print("Done")

    fs = 48000
    biquads = [
        #biquad.high_pass(100, 0.5, fs),
        #biquad.low_pass(5000, 0.5, fs),
        #        biquad.notch(800, 2, fs),
        biquad.Biquad.peaking_eq(1000, 2, -3, fs),
        biquad.Biquad.plain(),
    ]


def demo_beocreate():
    bc = dsptoolkit.DSPToolkit(
        xmlfile="/Users/matuschd/Dropbox/SigmaStudio/dspdac-2x16eq.xml",
        ip="192.168.4.184")
    bc.set_volume(0)
    print(bc.__dict__)

    filters = dsptoolkit.REW.readfilters(
        "/Users/matuschd/devel/python/hifiberry-dsp/sample_files/rew-filter-settings.txt")

    print(filters)

    filters = [filters[0]]

    bc.set_filters(filters, 0)

    bc.sigmatcp.write_decimal(185, 0)
    print(bc.sigmatcp.read_decimal(185))
    bc.sigmatcp.write_decimal(185, 1)
    print(bc.sigmatcp.read_decimal(185))
    bc.sigmatcp.write_decimal(185, 0.5)
    print(bc.sigmatcp.read_decimal(185))
    bc.sigmatcp.write_decimal(185, 0.1)
    print(bc.sigmatcp.read_decimal(185))
    bc.sigmatcp.write_decimal(185, 1.4)
    print(bc.sigmatcp.read_decimal(185))

    bc.clear_filters()


def main():

    demo_sigmatcp()
    demo_beocreate()


if __name__ == '__main__':
    main()
