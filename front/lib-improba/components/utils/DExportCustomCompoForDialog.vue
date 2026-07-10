<template>
  <!-- notice dialogRef here -->
  <q-dialog ref="dialogRef" @hide="onDialogHide">
    <q-card
      class="q-dialog-plugin text-text bg-background"
      style="width: 90rem !important"
    >
      <q-card-section>
        <div class="text-h6">Export de données</div>
      </q-card-section>

      <q-card-section>
        <p
          v-if="showWarning"
          style="color: white; height: 20px; padding-top: 10px"
        >
          <q-icon v-if="showWarning" name="warning" color="white" size="xs" />
          <i v-if="showWarning" style="padding-left: 7px">
            Les données exportées sont uniquement celles visibles à l'écran
          </i>
        </p>
      </q-card-section>

      <q-card-section>
        <q-form class="columns q-col-gutter-lg">
          <div class="row full-width">
            <div class="col-2 q-mr-sm" style="min-width: 10rem; max-height: 40px">
              <div class="fit text-text full-height q-mr-md row items-center">
                <div class="full-width ellipsis text-right text-weight-bold">
                  Nom du fichier
                </div>
              </div>
            </div>
            <div class="col">
              <q-input
                v-model="state.name"
                dense
                color="accent-medium"
                class="text-text"
              />
            </div>
          </div>
          <div class="row full-width">
            <div class="col-2 q-mr-sm" style="min-width: 10rem; max-height: 40px">
              <div class="fit text-text full-height q-mr-md row items-center">
                <div class="full-width ellipsis text-right text-weight-bold">
                  Format du fichier
                </div>
              </div>
            </div>
            <div class="col">
              <q-btn-toggle
                v-if="!excelOnly"
                v-model="state.type"
                :options="stateless.typeOptions"
              />
              <q-btn-toggle
                v-else
                v-model="state.type"
                :options="stateless.excelOption"
              />
            </div>
          </div>
        </q-form>
      </q-card-section>

      <!-- buttons example -->
      <q-card-section>
        <div class="row items-center justify-end full-width q-gutter-md">
          <q-btn flat no-caps @click="onCancelClick">
            {{ $t('components.buttons.DCancelBtn.label') }}
          </q-btn>
          <q-btn
            unelevated
            no-caps
            rounded
            color="accent-medium"
            label="Exporter"
            @click="onOKClick"
            :disable="state.name.length === 0"
          />
        </div>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script lang="ts">
import { defineComponent, reactive } from 'vue'
import { useDialogPluginComponent } from 'quasar'

export default defineComponent({
  props: {
    excelOnly: {
      type: Boolean,
      default: false,
    },
    showWarning: {
      type: Boolean,
      default: true,
    },
  },
  emits: [
    // REQUIRED; need to specify some events that your
    // component will emit through useDialogPluginComponent()
    ...useDialogPluginComponent.emits,
  ],

  setup() {
    // REQUIRED; must be called inside of setup()
    const { dialogRef, onDialogHide, onDialogOK, onDialogCancel } =
      useDialogPluginComponent()
    // dialogRef      - Vue ref to be applied to QDialog
    // onDialogHide   - Function to be used as handler for @hide on QDialog
    // onDialogOK     - Function to call to settle dialog with "ok" outcome
    //                    example: onDialogOK() - no payload
    //                    example: onDialogOK({ /*.../* }) - with payload
    // onDialogCancel - Function to call to settle dialog with "cancel" outcome

    const stateless = {
      typeOptions: [
        {
          label: 'CSV',
          value: 'csv',
        },
        {
          label: 'Excel',
          value: 'excel',
        },
      ],
      excelOption: [
        {
          label: 'Excel',
          value: 'excel',
        },
      ],
    }

    const state = reactive({
      name: '',
      type: 'excel',
    })

    return {
      // This is REQUIRED;
      // Need to inject these (from useDialogPluginComponent() call)
      // into the vue scope for the vue html template
      dialogRef,
      onDialogHide,

      // other methods that we used in our vue html template;
      // these are part of our example (so not required)
      onOKClick() {
        // on OK, it is REQUIRED to
        // call onDialogOK (with optional payload)
        onDialogOK({
          type: state.type,
          name: state.name,
        })
        // or with payload: onDialogOK({ ... })
        // ...and it will also hide the dialog automatically
      },

      // we can passthrough onDialogCancel directly
      onCancelClick: onDialogCancel,
      state,
      stateless,
    }
  },
})
</script>
