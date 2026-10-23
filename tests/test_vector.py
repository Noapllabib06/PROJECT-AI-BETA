import numpy as np
from turbovec import TurboQuantIndex

def test_run():
    print("Inisialisasi data vektor acak (Simulasi Embedding)...")
    dimensi = 768
    jumlah_data = 500
    
    # 1. Buat data vektor acak dan pastikan tipe datanya float32
    data_vektor = np.random.rand(jumlah_data, dimensi).astype(np.float32)
    
    # 2. Inisialisasi indeks menggunakan TurboQuantIndex (bit_width=2 untuk kompresi maksimal)
    print("Membuat indeks TurboQuantIndex dengan bit_width=2...")
    index = TurboQuantIndex(dim=dimensi, bit_width=2)
    
    # 3. Masukkan data ke dalam indeks
    index.add(data_vektor)
    print(f"Berhasil mengindeks {jumlah_data} data vektor!")
    
    # 4. Melakukan query pencarian kemiripan
    query = np.random.rand(1, dimensi).astype(np.float32)
    scores, indices = index.search(query, k=3)
    
    print("\n--- HASIL UJI COBA PENCARIAN TURBOVEC ---")
    for i in range(3):
        print(f"Peringkat {i+1} -> Indeks Slot: {indices[0][i]}, Skor: {scores[0][i]:.4f}")

if __name__ == "__main__":
    test_run()