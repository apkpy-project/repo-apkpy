package com.exemplo;

import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.Button;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.setTheme(androidx.appcompat.R.style.Theme_AppCompat_Light_NoActionBar);
        super.onCreate(savedInstanceState);
        
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);

        // O Python vai colocar os botões aqui:
        // INJECT_CODE_HERE

        setContentView(layout);
    }
}